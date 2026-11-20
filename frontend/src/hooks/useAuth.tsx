import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { getAccessToken, notifyAuthChanged, setAccessToken, subscribeAuth } from '@/services/apiClient'
import { login as apiLogin, logout as apiLogout, me as apiMe, refreshSession } from '@/services/authService'
import { setCacheScope } from '@/services/requestCache'
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
    let refreshedUser: User | null = null
    if (!getAccessToken()) {
      // The refresh endpoint already returns the user payload, so a separate
      // /auth/me/ request is unnecessary on a fresh load.
      refreshedUser = (await refreshSession())?.user ?? null
    }
    if (!getAccessToken()) {
      setUser(null)
      setLoading(false)
      return
    }
    try {
      setUser(refreshedUser ?? (await apiMe()))
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
      if (!getAccessToken()) {
        setUser(null)
        setCacheScope('anon')
      }
    })
  }, [refreshUser])

  // Private responses must never be shared across accounts. Changing scope
  // clears both cached and in-flight entries from the previous user.
  useEffect(() => {
    setCacheScope(user ? `user:${user.id}` : 'anon')
  }, [user?.id])

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
