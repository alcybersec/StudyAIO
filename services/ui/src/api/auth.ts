import { api } from './client'
import type {
  AccountDeletedResponse,
  AccountDeleteRequest,
  AuthConfig,
  AuthUser,
  ChangePasswordRequest,
  ForgotPasswordRequest,
  LoginRequest,
  MFASetupResponse,
  MFAVerifyRequest,
  MFAVerifyResponse,
  RegisterRequest,
  ResetPasswordRequest,
  SessionEndedResponse,
  UpdateProfileRequest,
  UserDataExport,
  VerifyEmailRequest,
} from '../types'

export const authApi = {
  config: () => api.get<AuthConfig>('/auth/config'),

  me: () => api.get<AuthUser>('/auth/me'),

  login: (data: LoginRequest) => api.post<AuthUser>('/auth/login', data),

  register: (data: RegisterRequest) => api.post<AuthUser>('/auth/register', data),

  logout: () => api.post<{ detail: string }>('/auth/logout'),

  refresh: () => api.post<{ detail: string }>('/auth/refresh'),

  changePassword: (data: ChangePasswordRequest) =>
    api.post<SessionEndedResponse>('/auth/change-password', data),

  forgotPassword: (data: ForgotPasswordRequest) =>
    api.post<{ detail: string }>('/auth/forgot-password', data),

  resetPassword: (data: ResetPasswordRequest) =>
    api.post<{ detail: string }>('/auth/reset-password', data),

  verifyEmail: (data: VerifyEmailRequest) =>
    api.post<{ detail: string }>('/auth/verify-email', data),

  resendVerification: () => api.post<{ detail: string }>('/auth/resend-verification'),

  updateProfile: (data: UpdateProfileRequest) => api.put<AuthUser>('/auth/me', data),

  mfaSetup: () => api.post<MFASetupResponse>('/auth/mfa/setup'),

  mfaVerify: (data: MFAVerifyRequest) =>
    api.post<MFAVerifyResponse>('/auth/mfa/verify', data),

  mfaDisable: (code: string) =>
    api.post<SessionEndedResponse>('/auth/mfa/disable', { totp_code: code }),

  exportData: () => api.get<UserDataExport>('/auth/account/export'),

  // DELETE with a body — `api.delete` sends none, so use the escape hatch.
  deleteAccount: (data: AccountDeleteRequest) =>
    api.request<AccountDeletedResponse>('/auth/account', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),
}
