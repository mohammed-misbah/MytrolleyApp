import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios'

const USER = {
  id: 1,
  username: 'tester',
  email: 'tester@example.test',
  first_name: 'Test',
  last_name: 'User',
  full_name: 'Test User',
  is_active: true,
  is_staff: true,
  date_joined: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-02T00:00:00Z',
  roles: ['Administrator'],
  permissions: ['accounts.manage_catalog'],
}

type Adapter = (config: InternalAxiosRequestConfig) => Promise<AxiosResponse>
type Call = { method: string; url: string; authorization?: string; contentType?: string }

function makeResponse(config: InternalAxiosRequestConfig, status: number, data: unknown): AxiosResponse {
  return { data, status, statusText: 'OK', headers: {}, config } as AxiosResponse
}

async function harness() {
  vi.resetModules()
  vi.stubGlobal('BroadcastChannel', class {
    static messages: unknown[] = []
    postMessage(data: unknown) {
      ;(BroadcastChannel as unknown as { messages: unknown[] }).messages.push(data)
    }
    close() {}
  })
  document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
  document.cookie = 'csrftoken=test-csrf; path=/'

  const axios = (await import('axios')).default
  const api = await import('./apiClient')
  const calls: Call[] = []
  const install = (adapter: Adapter) => {
    api.apiClient.defaults.adapter = adapter as never
    axios.defaults.adapter = adapter as never
  }
  return { axios, api, calls, install }
}

function fail(config: InternalAxiosRequestConfig, _axios: unknown, status: number, code: string) {
  const response = makeResponse(config, status, {
    error: { code, message: 'failed', fields: {}, request_id: '' },
  })
  return Promise.reject(
    new AxiosError('failed', 'ERR_BAD_RESPONSE', config, undefined, response as never),
  )
}

describe('JWT refresh integration', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  it('refreshes an expired access token and retries product creation exactly once', async () => {
    const { axios, api, calls, install } = await harness()
    let refreshCount = 0
    let createCount = 0

    install(async (config) => {
      const url = String(config.url)
      const method = String(config.method).toLowerCase()
      calls.push({
        method,
        url,
        authorization: String(config.headers.Authorization ?? ''),
        contentType: String(config.headers['Content-Type'] ?? ''),
      })
      if (url.includes('/auth/refresh/')) {
        refreshCount += 1
        return makeResponse(config, 200, {
          access: 'new-access',
          user: USER,
          token_type: 'Bearer',
          expires_in: 300,
        })
      }
      if (url.includes('create-with-relations')) {
        createCount += 1
        if (createCount === 1) return fail(config, axios, 401, 'TOKEN_INVALID')
        return makeResponse(config, 201, { id: 42 })
      }
      return makeResponse(config, 200, {})
    })

    api.setAccessToken('expired-access')
    const form = new FormData()
    form.append('name', 'Test')
    const response = await api.apiClient.post('/products/create-with-relations/', form)

    expect(response.status).toBe(201)
    expect(refreshCount).toBe(1)
    expect(createCount).toBe(2)
    expect(api.getAccessToken()).toBe('new-access')
    expect(calls.filter((call) => call.url.includes('create-with-relations'))[1].authorization).toBe(
      'Bearer new-access',
    )
    expect(calls.find((call) => call.url.includes('create-with-relations'))?.contentType).not.toContain(
      'application/json',
    )
  })

  it('renews the token for catalogService product creation, image upload and image update', async () => {
    vi.resetModules()
    document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
    document.cookie = 'csrftoken=test-csrf; path=/'
    const axios = (await import('axios')).default
    const api = await import('./apiClient')
    const catalog = await import('./catalogService')
    let refreshCount = 0
    const seen: Call[] = []

    const adapter: Adapter = async (config) => {
      const url = String(config.url)
      seen.push({
        method: String(config.method),
        url,
        authorization: String(config.headers.Authorization ?? ''),
      })
      if (url.includes('/auth/refresh/')) {
        refreshCount += 1
        return makeResponse(config, 200, { access: 'service-access', user: USER })
      }
      if (String(config.headers.Authorization) === 'Bearer expired-access') {
        return fail(config, axios, 401, 'TOKEN_INVALID')
      }
      return makeResponse(config, 200, { id: 1 })
    }
    api.apiClient.defaults.adapter = adapter as never
    axios.defaults.adapter = adapter as never

    api.setAccessToken('expired-access')
    const form = new FormData()
    form.append('name', 'Test')
    await catalog.catalogService.createProductWithRelations(form)
    const file = new File(['x'], 'x.png', { type: 'image/png' })
    await catalog.catalogService.uploadImage(1, file)
    await catalog.catalogService.updateImage(1, 2, { is_primary: true })

    expect(refreshCount).toBe(1)
    expect(seen.filter((call) => call.url.includes('create-with-relations'))).toHaveLength(2)
    expect(
      seen
        .filter((call) => !call.url.includes('/auth/refresh/'))
        .slice(-3)
        .every((call) => call.authorization === 'Bearer service-access'),
    ).toBe(true)
  })

  it('keeps the user signed in when refresh fails transiently', async () => {
    const { axios, api, install } = await harness()
    let refreshCount = 0
    let createCount = 0

    install(async (config) => {
      const url = String(config.url)
      if (url.includes('/auth/refresh/')) {
        refreshCount += 1
        return fail(config, axios, 500, 'SERVER_ERROR')
      }
      createCount += 1
      return fail(config, axios, 401, 'TOKEN_INVALID')
    })

    api.setAccessToken('still-valid')
    await expect(api.apiClient.post('/products/', { name: 'Test' })).rejects.toMatchObject({
      code: 'REFRESH_UNAVAILABLE',
    })
    expect(refreshCount).toBe(1)
    expect(createCount).toBe(1)
    expect(api.getAccessToken()).toBe('still-valid')
  })

  it('shares one refresh across concurrent expired requests', async () => {
    const { axios, api, install } = await harness()
    let refreshCount = 0
    let requestCount = 0

    install(async (config) => {
      const url = String(config.url)
      if (url.includes('/auth/refresh/')) {
        refreshCount += 1
        await new Promise((resolve) => setTimeout(resolve, 20))
        return makeResponse(config, 200, { access: 'shared-access', user: USER })
      }
      requestCount += 1
      if (String(config.headers.Authorization) === 'Bearer expired-access') {
        return fail(config, axios, 401, 'TOKEN_INVALID')
      }
      return makeResponse(config, 200, { ok: true })
    })

    api.setAccessToken('expired-access')
    const [first, second] = await Promise.all([
      api.apiClient.get('/products/'),
      api.apiClient.get('/categories/'),
    ])
    expect(first.status).toBe(200)
    expect(second.status).toBe(200)
    expect(refreshCount).toBe(1)
    expect(requestCount).toBe(4)
  })

  it('never replays a non-idempotent POST that reached the handler', async () => {
    const { axios, api, install } = await harness()
    let createCount = 0
    let refreshCount = 0

    install(async (config) => {
      const url = String(config.url)
      if (url.includes('/auth/refresh/')) {
        refreshCount += 1
        return makeResponse(config, 200, { access: 'new-access', user: USER })
      }
      createCount += 1
      return fail(config, axios, 401, 'VALIDATION_ERROR')
    })

    api.setAccessToken('expired-access')
    await expect(api.apiClient.post('/products/', { name: 'Test' })).rejects.toBeDefined()
    expect(createCount).toBe(1)
    expect(refreshCount).toBe(0)
  })
})

describe('cross-tab coordination', () => {
  beforeEach(() => {
    vi.unstubAllGlobals()
  })

  it('serialises refresh across tabs with Web Locks and broadcasts the new token', async () => {
    vi.resetModules()
    let active = 0
    let maxActive = 0
    let lockRequests = 0
    let queue: Promise<unknown> = Promise.resolve()
    Object.defineProperty(navigator, 'locks', {
      configurable: true,
      value: {
        request: (_name: string, fn: () => Promise<unknown>) => {
          lockRequests += 1
          const run = queue.then(async () => {
            active += 1
            maxActive = Math.max(maxActive, active)
            try {
              await new Promise((resolve) => setTimeout(resolve, 10))
              return await fn()
            } finally {
              active -= 1
            }
          })
          queue = run.catch(() => undefined)
          return run
        },
      },
    })
    vi.stubGlobal('BroadcastChannel', class {
      postMessage(data: unknown) {
        ;(globalThis as unknown as { __messages: unknown[] }).__messages ??= []
        ;(globalThis as unknown as { __messages: unknown[] }).__messages.push(data)
      }
      close() {}
    })
    document.cookie = 'csrftoken=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
    document.cookie = 'csrftoken=test-csrf; path=/'

    const axios = (await import('axios')).default
    const api = await import('./apiClient')
    let refreshCount = 0
    axios.defaults.adapter = (async (config: InternalAxiosRequestConfig) => {
      refreshCount += 1
      return makeResponse(config, 200, { access: `token-${refreshCount}`, user: USER })
    }) as never

    await Promise.all([api.withRefreshLock(async () => 'a'), api.withRefreshLock(async () => 'b')])
    expect(maxActive).toBe(1)
    expect(lockRequests).toBe(2)

    const outcome = await api.refreshSession()
    expect(outcome.ok).toBe(true)
    expect(refreshCount).toBe(1)
    const messages = (globalThis as unknown as { __messages?: unknown[] }).__messages ?? []
    expect(messages.some((message) => (message as { access?: string }).access === 'token-1')).toBe(true)
  })
})
