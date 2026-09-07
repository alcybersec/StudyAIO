import { createContext, useCallback, useEffect, type ReactNode } from 'react'
import { useQuery, useQueryClient, useMutation, type QueryClient } from '@tanstack/react-query'
import { authApi } from '../api/auth'
import { SELF_HOSTED_OWNER, type QueueOwner } from '../lib/queueOwner'
import { reconcileSession } from '../lib/sessionScope'
import type { AuthConfig, AuthUser, LoginRequest, RegisterRequest } from '../types'

export interface AuthContextValue {
  user: AuthUser | null
  authConfig: AuthConfig | null
  isAuthenticated: boolean
  isLoading: boolean
  isSelfHosted: boolean
  isDemo: boolean
  login: (data: LoginRequest) => Promise<AuthUser>
  register: (data: RegisterRequest) => Promise<AuthUser>
  logout: () => Promise<void>
}

// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext<AuthContextValue | null>(null)

/**
 * Purge everything the browser is holding for the previous identity: the
 * service worker's per-user API caches, the offline write queue's ownership
 * marker, and react-query's in-memory data.
 *
 * Auth queries are deliberately left alone. Clearing `['auth', 'config']`
 * would make `isSelfHosted` fall back to `true` for a frame, which reads as
 * "authenticated" and would keep a signed-out user inside the app.
 *
 * `resetQueries`, not `removeQueries`: removing a query that still has mounted
 * observers drops it from the cache underneath them. `resetQueries` clears the
 * data — which is the whole point here — and lets the observers refetch
 * cleanly. `reconcileSession` also guarantees this never runs on a first page
 * load, where there is no previous identity and nothing to purge.
 */
function purgeSessionState(identity: QueueOwner, queryClient: QueryClient) {
  return reconcileSession(identity, {
    onIdentityChange: () => {
      void queryClient.resetQueries({ predicate: (query) => query.queryKey[0] !== 'auth' })
    },
  })
}

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
    // Awaited here so the caller can navigate knowing the purge is done. The
    // effect below would catch this too; `reconcileSession` is serialised and
    // no-ops on the second call.
    await purgeSessionState(null, queryClient)
  }, [logoutMutation, queryClient])

  const isLoading = configLoading || (!isSelfHosted && userLoading)
  const isAuthenticated = !!user || isSelfHosted
  const isDemo = user?.role === 'demo'

  // Keep persisted browser state tied to whoever is signed in.
  //
  // This watches the identity rather than hooking the logout button, because
  // most sessions end without anyone clicking logout — the refresh token
  // lapses, or an admin revokes it, and `['auth', 'me']` simply stops
  // resolving to a user. That path has to purge too, otherwise the hole this
  // closes stays open for the common case.
  //
  // `isLoading` gates it so the undefined-while-fetching state of the `me`
  // query is not mistaken for a sign-out, which would wipe the offline caches
  // on every page load.
  const identity: QueueOwner = isSelfHosted ? SELF_HOSTED_OWNER : (user?.id ?? null)
  useEffect(() => {
    if (isLoading) return
    void purgeSessionState(identity, queryClient)
  }, [isLoading, identity, queryClient])

  return (
    <AuthContext.Provider
      value={{
        user: user ?? null,
        authConfig: authConfig ?? null,
        isAuthenticated,
        isLoading,
        isSelfHosted,
        isDemo,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}
