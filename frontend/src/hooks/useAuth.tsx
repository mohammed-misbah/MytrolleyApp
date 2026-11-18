import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { getAccessToken, notifyAuthChanged, setAccessToken, subscribeAuth } from '@/services/apiClient'
import { login as apiLogin, logout as apiLogout, me as apiMe, refreshSession } from '@/services/authService'
import type { User } from '@/types'

interface AuthContextValue {
  user: User | null
  token: string | null
  loading: boolean
  signIn: (username: string, password: string) => Promise<void>
  signOut: () => Promise<void>
  refreshUser: () => Promise<void>
  hasPermission: (code: string) => boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(getAccessToken())
  const [loading, setLoading] = useState(true)

  const refreshUser = useCallback(async () => {
    if (!getAccessToken()) {
      // The refresh token lives only in an HttpOnly cookie. On a fresh load,
      // exchange it for an in-memory access token using the readable CSRF cookie.
      await refreshSession()
    }
    if (!getAccessToken()) {
      setUser(null)
      setLoading(false)
      return
    }
    try {
      setUser(await apiMe())
      setToken(getAccessToken())
    } catch {
      setAccessToken(null)
      setUser(null)
      setToken(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refreshUser()
    return subscribeAuth(() => {
      setToken(getAccessToken())
      if (!getAccessToken()) setUser(null)
    })
  }, [refreshUser])

  const signIn = useCallback(async (username: string, password: string) => {
    const response = await apiLogin(username, password)
    setToken(getAccessToken())
    setUser(response.user)
    notifyAuthChanged()
  }, [])

  const signOut = useCallback(async () => {
    try {
      await apiLogout()
    } finally {
      setAccessToken(null)
      setToken(null)
      setUser(null)
      notifyAuthChanged()
    }
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      loading,
      signIn,
      signOut,
      refreshUser,
      hasPermission: (code: string) => Boolean(user?.permissions?.includes(code)),
    }),
    [user, token, loading, signIn, signOut, refreshUser],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within AuthProvider')
  return context
}
