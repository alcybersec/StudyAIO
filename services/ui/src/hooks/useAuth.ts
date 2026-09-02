import { useCallback, useContext } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { AuthContext, type AuthContextValue } from '../contexts/AuthContext'
import { authApi } from '../api/auth'
import type { ChangePasswordRequest, MFAVerifyRequest, UpdateProfileRequest } from '../types'

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return ctx
}

/** Reasons the server ended a session on purpose; read by LoginPage. */
export type SessionEndedReason = 'password_changed' | 'mfa_disabled'

/**
 * Hand the user off to /login after an action that ended their session.
 *
 * Changing a password or disabling MFA stamps `tokens_valid_from` server-side,
 * so the cookies this tab is holding are already dead. Dropping the cached user
 * and navigating in the same update matters: do them separately and
 * ProtectedRoute wins the race and bounces to a bare /login, losing the reason
 * the user is being asked to sign in again.
 */
export function useSessionHandoff() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  return useCallback(
    (reason: SessionEndedReason) => {
      queryClient.setQueryData(['auth', 'me'], null)
      queryClient.removeQueries({ queryKey: ['auth', 'me'] })
      navigate(`/login?reason=${reason}`, { replace: true })
    },
    [queryClient, navigate],
  )
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (data: ChangePasswordRequest) => authApi.changePassword(data),
  })
}

export function useUpdateProfile() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: UpdateProfileRequest) => authApi.updateProfile(data),
    onSuccess: (data) => {
      queryClient.setQueryData(['auth', 'me'], data)
    },
  })
}

export function useMFASetup() {
  return useMutation({
    mutationFn: () => authApi.mfaSetup(),
  })
}

export function useMFAVerify() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: MFAVerifyRequest) => authApi.mfaVerify(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['auth', 'me'] })
    },
  })
}

export function useMFADisable() {
  // No cache invalidation here: disabling MFA ends the session, so refetching
  // /auth/me would only 401. Callers run useSessionHandoff instead.
  return useMutation({
    mutationFn: (code: string) => authApi.mfaDisable(code),
  })
}
