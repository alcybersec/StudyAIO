import { api } from './client'
import type {
  DiagnosticResponse,
  TargetedGeneration,
  TargetedKind,
  TonightPlan,
  WeakSpotsResponse,
} from '../types'

/** api.weak-spots v1 (docs/CONTRACTS.md). */
export const weakSpotsApi = {
  list: (courseId?: string) =>
    api.get<WeakSpotsResponse>(
      `/weak-spots${courseId ? `?${new URLSearchParams({ course_id: courseId })}` : ''}`,
    ),
  diagnostic: (courseId: string, week: number) =>
    api.get<DiagnosticResponse>(
      `/weak-spots/diagnostic?${new URLSearchParams({ course_id: courseId, week: String(week) })}`,
    ),
  /** 202 (new) and 200 (the in-flight one) carry the same body, so both are one call. */
  requestTargeted: (body: { course_id: string; week: number; kind: TargetedKind }) =>
    api.post<TargetedGeneration>('/weak-spots/targeted', body),
  targeted: (generationId: string) =>
    api.get<TargetedGeneration>(`/weak-spots/targeted/${encodeURIComponent(generationId)}`),
  tonight: () => api.get<TonightPlan>('/study-plan/tonight'),
  refreshTonight: () => api.post<TonightPlan>('/study-plan/tonight/refresh', {}),
}
