import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { weakSpotsApi } from '../api/weakSpots'
import { isGenerationActive } from '../lib/weakSpots'
import type { TargetedGeneration, TargetedKind } from '../types'

/** How often a queued/running generation is re-read. */
export const GENERATION_POLL_MS = 2000

export const weakSpotKeys = {
  all: ['weak-spots'] as const,
  list: (courseId?: string) => ['weak-spots', 'list', courseId ?? null] as const,
  tonight: ['weak-spots', 'tonight'] as const,
}

export function useWeakSpots(courseId?: string) {
  return useQuery({
    queryKey: weakSpotKeys.list(courseId),
    queryFn: () => weakSpotsApi.list(courseId),
  })
}

export function useTonightPlan() {
  return useQuery({
    queryKey: weakSpotKeys.tonight,
    queryFn: weakSpotsApi.tonight,
  })
}

export function useRefreshTonightPlan() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: weakSpotsApi.refreshTonight,
    onSuccess: (plan) => queryClient.setQueryData(weakSpotKeys.tonight, plan),
  })
}

/** Starts the diagnostic set: the API picks the existing questions; nothing is generated here. */
export function useDiagnostic() {
  return useMutation({
    mutationFn: ({ courseId, week }: { courseId: string; week: number }) =>
      weakSpotsApi.diagnostic(courseId, week),
  })
}

export function useRequestTargeted() {
  return useMutation({
    mutationFn: (body: { course_id: string; week: number; kind: TargetedKind }) =>
      weakSpotsApi.requestTargeted(body),
  })
}

/** Polls one generation until it is completed or failed. */
export function useTargetedGeneration(generationId: string | null) {
  return useQuery<TargetedGeneration>({
    queryKey: ['weak-spots', 'targeted', generationId],
    queryFn: () => weakSpotsApi.targeted(generationId as string),
    enabled: !!generationId,
    refetchInterval: (query) =>
      isGenerationActive(query.state.data) || !query.state.data ? GENERATION_POLL_MS : false,
  })
}
