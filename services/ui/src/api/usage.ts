import { api } from './client'

export type UsageEventName = 'summary_viewed' | 'study_plan_viewed'

/**
 * Fire-and-forget view event (services.usage v1). Never throws and never
 * blocks the caller: a failed event is not worth a toast. The endpoint answers
 * 204, which the client's JSON parse rejects; that rejection is swallowed too.
 */
export function recordUsageEvent(event: UsageEventName, courseId?: string | null): void {
  api
    .post<unknown>('/usage-events', courseId ? { event, course_id: courseId } : { event })
    .catch(() => {})
}
