import { createContext, useCallback, type ReactNode } from 'react'
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query'
import { authApi } from '../api/auth'
import type { AuthConfig, AuthUser, LoginRequest, RegisterRequest } from '../types'

export interface AuthContextValue {
  user: AuthUser | null
  authConfig: AuthConfig | null
  isAuthenticated: boolean
  isLoading: boolean
  isSelfHosted: boolean
  login: (data: LoginRequest) => Promise<AuthUser>
  register: (data: RegisterRequest) => Promise<AuthUser>
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()

  const { data: authConfig, isLoading: configLoading } = useQuery({
    queryKey: ['auth', 'config'],
    queryFn: authApi.config,
    staleTime: Infinity,
    retry: 1,
  })

  const isSelfHosted = authConfig?.self_hosted ?? true

  const {
    data: user,
    isLoading: userLoading,
  } = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: authApi.me,
    retry: false,
    enabled: !isSelfHosted && !configLoading,
  })

  const loginMutation = useMutation({
    mutationFn: authApi.login,
    onSuccess: (data) => {
      queryClient.setQueryData(['auth', 'me'], data)
    },
  })

  const registerMutation = useMutation({
    mutationFn: authApi.register,
    onSuccess: (data) => {
      queryClient.setQueryData(['auth', 'me'], data)
    },
  })

  const logoutMutation = useMutation({
    mutationFn: authApi.logout,
    onSuccess: () => {
      queryClient.setQueryData(['auth', 'me'], null)
      queryClient.removeQueries({ queryKey: ['auth', 'me'] })
    },
  })

  const login = useCallback(
    async (data: LoginRequest) => {
      return loginMutation.mutateAsync(data)
    },
    [loginMutation],
  )

  const register = useCallback(
    async (data: RegisterRequest) => {
      return registerMutation.mutateAsync(data)
    },
    [registerMutation],
  )

  const logout = useCallback(async () => {
    await logoutMutation.mutateAsync()
  }, [logoutMutation])

  const isLoading = configLoading || (!isSelfHosted && userLoading)
  const isAuthenticated = !!user || isSelfHosted

  return (
    <AuthContext.Provider
      value={{
        user: user ?? null,
        authConfig: authConfig ?? null,
        isAuthenticated,
        isLoading,
        isSelfHosted,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}
