import { apiClient, setAccessToken } from './apiClient'
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

export async function me(): Promise<User> {
  const { data } = await apiClient.get<User>('/auth/me/')
  return data
}
