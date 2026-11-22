import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { api, authToken, onUnauthorized } from '../../api/api-client'
import type { CurrentUser } from '../../api/types'
import { AuthContext } from './auth-context'

interface TokenResponse { token: string; user: CurrentUser }

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null)
  const [isLoading, setIsLoading] = useState(authToken.get() !== null)

  const refreshUser = useCallback(async () => {
    setUser(await api.get<CurrentUser>('/auth/me/'))
  }, [])

  useEffect(() => {
    onUnauthorized(() => { authToken.clear(); setUser(null) })
    if (!authToken.get()) return
    refreshUser().catch(() => authToken.clear()).finally(() => setIsLoading(false))
  }, [refreshUser])

  const value = useMemo(() => ({
    user,
    isLoading,
    refreshUser,
    login: async (username: string, password: string) => {
      const response = await api.post<TokenResponse>('/auth/login/', { username, password })
      authToken.set(response.token)
      setUser(response.user)
    },
    logout: async () => {
      await api.post('/auth/logout/').catch(() => undefined)
      authToken.clear()
      setUser(null)
    },
  }), [user, isLoading, refreshUser])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
