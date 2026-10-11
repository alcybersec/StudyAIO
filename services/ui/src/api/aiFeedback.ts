import { api } from './client'
import type { AIFeedbackPut, AIFeedbackTargetType, AIFeedbackVote } from '../types'

/** Per-item thumbs up/down on AI output (api.ai_feedback v1). Not the app-bug inbox in feedback.ts. */
export const aiFeedbackApi = {
  async mine(targetType: AIFeedbackTargetType, targetIds: string[]): Promise<AIFeedbackVote[]> {
    const qs = new URLSearchParams({ target_type: targetType })
    for (const id of targetIds.slice(0, 100)) qs.append('target_ids', id)
    const res = await api.get<{ items: AIFeedbackVote[] }>(`/feedback/mine?${qs}`)
    return res.items
  },

  put: (body: AIFeedbackPut) => api.put<AIFeedbackVote>('/feedback', body),

  clear: (targetType: AIFeedbackTargetType, targetId: string) =>
    api.delete(`/feedback/${targetType}/${encodeURIComponent(targetId)}`),
}
