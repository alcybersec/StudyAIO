import { api } from './client'
import type {
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
  UpdateProfileRequest,
} from '../types'

export const authApi = {
  config: () => api.get<AuthConfig>('/auth/config'),

  me: () => api.get<AuthUser>('/auth/me'),

  login: (data: LoginRequest) => api.post<AuthUser>('/auth/login', data),

  register: (data: RegisterRequest) => api.post<AuthUser>('/auth/register', data),

  logout: () => api.post<{ detail: string }>('/auth/logout'),

  refresh: () => api.post<{ detail: string }>('/auth/refresh'),

  changePassword: (data: ChangePasswordRequest) =>
    api.post<{ detail: string }>('/auth/change-password', data),

  forgotPassword: (data: ForgotPasswordRequest) =>
    api.post<{ detail: string }>('/auth/forgot-password', data),

  resetPassword: (data: ResetPasswordRequest) =>
    api.post<{ detail: string }>('/auth/reset-password', data),

  updateProfile: (data: UpdateProfileRequest) => api.put<AuthUser>('/auth/me', data),

  mfaSetup: () => api.post<MFASetupResponse>('/auth/mfa/setup'),

  mfaVerify: (data: MFAVerifyRequest) =>
    api.post<MFAVerifyResponse>('/auth/mfa/verify', data),

  mfaDisable: (code: string) =>
    api.post<{ detail: string }>('/auth/mfa/disable', { totp_code: code }),
}
