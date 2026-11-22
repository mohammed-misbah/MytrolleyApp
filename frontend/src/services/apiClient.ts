import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import type { ApiErrorShape, User } from '@/types'
import { invalidateCache } from './requestCache'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export class ApiError extends Error {
  code: string
  fields: Record<string, string[]>
  requestId: string
  status: number

  constructor(status: number, body: ApiErrorShape) {
    super(body.message || 'Something went wrong.')
    this.status = status
    this.code = body.code || 'API_ERROR'
    this.fields = body.fields || {}
    this.requestId = body.request_id || ''
    this.name = 'ApiError'
  }

  get fieldMessages(): string[] {
    return Object.values(this.fields).flat()
  }
}

let accessToken: string | null = null
let authListeners: Array<() => void> = []

export function setAccessToken(token: string | null) {
  accessToken = token
}

export function getAccessToken() {
  return accessToken
}

export function subscribeAuth(listener: () => void) {
  authListeners.push(listener)
  return () => {
    authListeners = authListeners.filter((l) => l !== listener)
  }
}

export function notifyAuthChanged() {
  invalidateCache()
  authListeners.forEach((l) => l())
}

function getCsrfCookie(): string | null {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : null
}

function extractError(error: AxiosError): ApiError {
  const data = error.response?.data as { error?: ApiErrorShape } | undefined
  if (data?.error) {
    return new ApiError(error.response?.status ?? 0, data.error)
  }
  return new ApiError(error.response?.status ?? 0, {
    code: 'NETWORK_ERROR',
    message: error.message || 'Unable to reach the server.',
    fields: {},
    request_id: '',
  })
}

export const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
})

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }
  // Let the browser/axios supply the multipart boundary. The client default is
  // application/json, which would otherwise corrupt FormData uploads.
  if (typeof FormData !== 'undefined' && config.data instanceof FormData) {
    config.headers.delete('Content-Type')
  }
  return config
})

// Refresh codes emitted by /auth/refresh/ that mean the session is genuinely
// over. Everything else (network, 429, 5xx, CSRF mismatch) is transient.
const INVALID_REFRESH_CODES = new Set([
  'INVALID_REFRESH_TOKEN',
  'REFRESH_REUSE_DETECTED',
  'SESSION_REVOKED',
  'TOKEN_INVALID',
  'UNAUTHENTICATED',
])

// These 401s cannot be repaired by rotating a refresh token.
const UNRECOVERABLE_REQUEST_CODES = new Set(['SESSION_REVOKED', 'INVALID_CREDENTIALS'])

// DRF runs authentication in APIView.initial(), before the view method. A 401
// carrying one of these codes therefore proves the request was rejected before
// any handler ran. Only such a 401 is safe to replay after a refresh — a POST
// that reached a view must never be retried automatically (duplicate creation).
const PRE_HANDLER_AUTH_CODES = new Set(['TOKEN_INVALID', 'UNAUTHENTICATED'])

function errorCodeOf(error: AxiosError): string {
  const data = error.response?.data as { error?: ApiErrorShape } | undefined
  return data?.error?.code ?? ''
}

apiClient.interceptors.response.use(
  (response) => {
    const method = response.config.method?.toLowerCase()
    if (method && !['get', 'head', 'options'].includes(method)) {
      invalidateCache()
    }
    return response
  },
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined
    if (
      error.response?.status !== 401 ||
      !original ||
      original._retry ||
      !getAccessToken()
    ) {
      return Promise.reject(extractError(error))
    }

    const code = errorCodeOf(error)
    if (UNRECOVERABLE_REQUEST_CODES.has(code)) {
      // Revoked session: refreshing cannot help. Send the user to login.
      setAccessToken(null)
      notifyAuthChanged()
      return Promise.reject(extractError(error))
    }
    if (!PRE_HANDLER_AUTH_CODES.has(code)) {
      // Not proven to be a pre-handler auth rejection. Never replay it.
      return Promise.reject(extractError(error))
    }

    original._retry = true
    const outcome = await refreshSession()
    if (outcome.ok) {
      original.headers.Authorization = `Bearer ${outcome.access}`
      return apiClient(original)
    }
    if (outcome.kind === 'invalid') {
      setAccessToken(null)
      notifyAuthChanged()
      return Promise.reject(extractError(error))
    }
    // Transient refresh failure: the session is still valid. Keep the user
    // signed in and report a retryable error instead of redirecting to login.
    return Promise.reject(
      new ApiError(error.response.status, {
        code: 'REFRESH_UNAVAILABLE',
        message: 'Your session could not be renewed. Please try again.',
        fields: {},
        request_id: '',
      }),
    )
  },
)

export function toError(error: unknown): ApiError {
  if (error instanceof ApiError) return error
  if (axios.isAxiosError(error)) return extractError(error)
  return new ApiError(0, {
    code: 'UNKNOWN',
    message: 'Unexpected error.',
    fields: {},
    request_id: '',
  })
}

// ---------------------------------------------------------------------------
// Cross-tab refresh coordination
// ---------------------------------------------------------------------------
// Refresh tokens rotate. Two tabs refreshing with the same cookie make one
// look like a replay, and the API revokes the whole token family. A per-tab
// promise is not enough: the Web Locks API serialises refresh across every tab
// of this origin. BroadcastChannel then shares the resulting access token so
// other tabs do not need a redundant refresh at all.

const REFRESH_LOCK_NAME = 'mytrolley:refresh'
const REFRESH_LEASE_KEY = 'mytrolley:refresh-lease'
const AUTH_CHANNEL_NAME = 'mytrolley:auth'

type LockLike = {
  request: (name: string, callback: () => Promise<unknown>) => Promise<unknown>
}

type AuthBroadcast = { type: 'access-token'; access: string; at: number }

function getWebLocks(): LockLike | null {
  if (typeof navigator === 'undefined') return null
  return (navigator as Navigator & { locks?: LockLike }).locks ?? null
}

let authChannel: BroadcastChannel | null = null

function getAuthChannel(): BroadcastChannel | null {
  if (typeof BroadcastChannel === 'undefined') return null
  if (!authChannel) {
    authChannel = new BroadcastChannel(AUTH_CHANNEL_NAME)
    authChannel.onmessage = (event: MessageEvent<AuthBroadcast>) => {
      const data = event.data
      if (data?.type === 'access-token' && typeof data.access === 'string') {
        setAccessToken(data.access)
        notifyAuthChanged()
      }
    }
  }
  return authChannel
}

function broadcastAccessToken(access: string): void {
  getAuthChannel()?.postMessage({ type: 'access-token', access, at: Date.now() })
}

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function randomId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`
}

type Lease = { owner: string; expires: number }

function readLease(): Lease | null {
  if (typeof localStorage === 'undefined') return null
  try {
    const raw = localStorage.getItem(REFRESH_LEASE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Lease
    return typeof parsed.owner === 'string' && typeof parsed.expires === 'number' ? parsed : null
  } catch {
    return null
  }
}

/** Fallback for browsers without Web Locks: a short, owner-checked lease. */
async function acquireLease(): Promise<() => void> {
  if (typeof localStorage === 'undefined') return () => undefined
  const owner = randomId()
  const deadline = Date.now() + 5000
  while (Date.now() < deadline) {
    const current = readLease()
    if (!current || current.owner === owner || current.expires < Date.now()) {
      const lease: Lease = { owner, expires: Date.now() + 5000 }
      try {
        localStorage.setItem(REFRESH_LEASE_KEY, JSON.stringify(lease))
      } catch {
        return () => undefined
      }
      // Re-read after a tick so two tabs that raced cannot both own the lease.
      await delay(25)
      if (readLease()?.owner === owner) {
        return () => {
          if (readLease()?.owner === owner) {
            try {
              localStorage.removeItem(REFRESH_LEASE_KEY)
            } catch {
              // A stale lease expires on its own.
            }
          }
        }
      }
    }
    await delay(30)
  }
  // Never block authentication indefinitely on a broken storage backend.
  return () => undefined
}

/** Run a refresh while holding an origin-wide lock (or a lease fallback). */
export async function withRefreshLock<T>(fn: () => Promise<T>): Promise<T> {
  const locks = getWebLocks()
  if (locks) {
    return (await locks.request(REFRESH_LOCK_NAME, fn)) as T
  }
  const release = await acquireLease()
  try {
    return await fn()
  } finally {
    release()
  }
}

// ---------------------------------------------------------------------------
// Refresh
// ---------------------------------------------------------------------------

export type RefreshOutcome =
  | { ok: true; access: string; user: User }
  | { ok: false; kind: 'invalid' | 'network' | 'rate_limited' | 'server' | 'csrf' }

export type RefreshFailureKind = Exclude<RefreshOutcome, { ok: true }>['kind']

export function isTransientRefreshFailure(kind: RefreshFailureKind): boolean {
  return kind !== 'invalid'
}

interface RefreshResult {
  access: string
  user: User
}

function classifyRefreshError(error: unknown): RefreshOutcome {
  if (!axios.isAxiosError(error) || error.response === undefined) {
    return { ok: false, kind: 'network' }
  }
  const status = error.response.status
  if (status === 429) return { ok: false, kind: 'rate_limited' }
  if (status >= 500) return { ok: false, kind: 'server' }
  const body = error.response.data as { error?: ApiErrorShape } | undefined
  const code = body?.error?.code ?? ''
  if (INVALID_REFRESH_CODES.has(code)) return { ok: false, kind: 'invalid' }
  if (status === 403 && code === 'CSRF_FAILED') return { ok: false, kind: 'csrf' }
  // The refresh endpoint only emits authentication errors on 4xx. An
  // unrecognised 401/400/403 still means this browser cannot renew the session.
  return { ok: false, kind: 'invalid' }
}

async function requestRefresh(): Promise<RefreshOutcome> {
  const csrf = getCsrfCookie()
  if (!csrf) return { ok: false, kind: 'invalid' }
  try {
    const response = await axios.post<RefreshResult>(
      `${BASE_URL}/auth/refresh/`,
      {},
      {
        withCredentials: true,
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrf,
        },
      },
    )
    setAccessToken(response.data.access)
    broadcastAccessToken(response.data.access)
    return { ok: true, access: response.data.access, user: response.data.user }
  } catch (error) {
    return classifyRefreshError(error)
  }
}

let refreshInFlight: Promise<RefreshOutcome> | null = null

/** Exchange the HttpOnly refresh cookie for a new access token and user payload.
 * Single-flight per tab plus an origin-wide lock: refresh tokens rotate, so
 * parallel refreshes would look like reuse and revoke the whole session family. */
export function refreshSession(): Promise<RefreshOutcome> {
  if (refreshInFlight) return refreshInFlight
  refreshInFlight = withRefreshLock(requestRefresh).finally(() => {
    refreshInFlight = null
  })
  return refreshInFlight
}
