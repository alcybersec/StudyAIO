import { api } from './client'
import type {
  AdminUser,
  AdminUserCreated,
  AdminUserCreateRequest,
  AdminUserDeleted,
  AdminUserDetail,
  AdminUserLink,
  AdminUserList,
  AdminUserUpdate,
  InviteCode,
  InviteCodeList,
  InviteCreateRequest,
  SystemMetrics,
} from '../types'

export const adminApi = {
  listUsers(params?: {
    role?: string
    tier?: string
    is_active?: boolean
    offset?: number
    limit?: number
  }): Promise<AdminUserList> {
    const searchParams = new URLSearchParams()
    if (params?.role) searchParams.set('role', params.role)
    if (params?.tier) searchParams.set('tier', params.tier)
    if (params?.is_active !== undefined) searchParams.set('is_active', String(params.is_active))
    if (params?.offset !== undefined) searchParams.set('offset', String(params.offset))
    if (params?.limit !== undefined) searchParams.set('limit', String(params.limit))
    const qs = searchParams.toString()
    return api.get<AdminUserList>(`/admin/users${qs ? `?${qs}` : ''}`)
  },

  updateUser(userId: string, data: AdminUserUpdate): Promise<AdminUser> {
    return api.patch<AdminUser>(`/admin/users/${userId}`, data)
  },

  getMetrics(): Promise<SystemMetrics> {
    return api.get<SystemMetrics>('/admin/metrics')
  },

  getUserDetails(userId: string): Promise<AdminUserDetail> {
    return api.get<AdminUserDetail>(`/admin/users/${userId}/details`)
  },

  createUser(data: AdminUserCreateRequest): Promise<AdminUserCreated> {
    return api.post<AdminUserCreated>('/admin/users', data)
  },

  deleteUser(userId: string): Promise<AdminUserDeleted> {
    return api.request<AdminUserDeleted>(`/admin/users/${userId}`, { method: 'DELETE' })
  },

  sendPasswordReset(userId: string): Promise<AdminUserLink> {
    return api.post<AdminUserLink>(`/admin/users/${userId}/password-reset`)
  },

  resendVerification(userId: string): Promise<AdminUserLink> {
    return api.post<AdminUserLink>(`/admin/users/${userId}/resend-verification`)
  },

  listInvites(): Promise<InviteCodeList> {
    return api.get<InviteCodeList>('/admin/invites')
  },

  createInvite(data: InviteCreateRequest): Promise<InviteCode> {
    return api.post<InviteCode>('/admin/invites', data)
  },

  revokeInvite(inviteId: string): Promise<InviteCode> {
    return api.request<InviteCode>(`/admin/invites/${inviteId}`, { method: 'DELETE' })
  },
}
