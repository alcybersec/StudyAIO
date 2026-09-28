import { api } from './client'
import type { Feedback, FeedbackList, FeedbackRequest, FeedbackStatus } from '../types'

export const feedbackApi = {
  submit(body: FeedbackRequest): Promise<Feedback> {
    return api.post<Feedback>('/feedback', body)
  },

  list(params: { status?: FeedbackStatus; kind?: string; limit?: number } = {}): Promise<FeedbackList> {
    const qs = new URLSearchParams()
    if (params.status) qs.set('status', params.status)
    if (params.kind) qs.set('kind', params.kind)
    if (params.limit) qs.set('limit', String(params.limit))
    const suffix = qs.toString() ? `?${qs}` : ''
    return api.get<FeedbackList>(`/admin/feedback${suffix}`)
  },

  setStatus(id: string, status: FeedbackStatus): Promise<Feedback> {
    return api.patch<Feedback>(`/admin/feedback/${id}`, { status })
  },
}
