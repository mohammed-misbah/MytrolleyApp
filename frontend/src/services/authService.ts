import { apiClient, setAccessToken } from './apiClient'
import { dedupGet } from './requestCache'
import type { LoginResponse, User } from '@/types'

export { refreshSession } from './apiClient'

export async function login(username: string, password: string): Promise<LoginResponse> {
  const { data } = await apiClient.post<LoginResponse>('/auth/login/', { username, password })
  setAccessToken(data.access)
  return data
}

export async function logout(): Promise<void> {
  await apiClient.post('/auth/logout/')
  setAccessToken(null)
}

export function me(): Promise<User> {
  return dedupGet('auth:me', async () => (await apiClient.get<User>('/auth/me/')).data)
}
