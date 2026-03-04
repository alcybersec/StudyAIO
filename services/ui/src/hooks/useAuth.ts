import { useContext } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
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
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (code: string) => authApi.mfaDisable(code),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['auth', 'me'] })
    },
  })
}
