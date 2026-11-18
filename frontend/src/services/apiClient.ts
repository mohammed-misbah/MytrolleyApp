import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import type { ApiErrorShape } from '@/types'

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
  // GET/HEAD/DELETE on catalog endpoints require no CSRF; only cookie refresh does.
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _retry?: boolean }
    if (error.response?.status === 401 && !original._retry && accessToken) {
      original._retry = true
      const next = await refreshSession()
      if (next) {
        original.headers.Authorization = `Bearer ${next}`
        return apiClient(original)
      }
      setAccessToken(null)
      notifyAuthChanged()
    }
    return Promise.reject(extractError(error))
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

export function multipartHeaders(): Record<string, string> {
  return accessToken ? { Authorization: `Bearer ${accessToken}` } : {}
}

let refreshInFlight: Promise<string | null> | null = null

/** Exchange the HttpOnly refresh cookie for a new in-memory access token.
 * Single-flight: refresh tokens rotate, so two concurrent calls would make one
 * look like reuse and revoke the whole session family. */
export function refreshSession(): Promise<string | null> {
  if (refreshInFlight) return refreshInFlight
  refreshInFlight = (async () => {
    const csrf = getCsrfCookie()
    if (!csrf) return null
    try {
      const response = await axios.post<{ access: string }>(
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
      return response.data.access
    } catch {
      return null
    } finally {
      refreshInFlight = null
    }
  })()
  return refreshInFlight
}
