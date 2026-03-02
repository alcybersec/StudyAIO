import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { assetsApi, coursesApi, dashboardApi, qaApi, reviewApi, settingsApi, studyApi, uploadApi } from '../api/endpoints'
import type { QARequest, ReviewRequest, SettingsUpdate } from '../types'

export function useDashboard() {
  return useQuery({
    queryKey: ['dashboard'],
    queryFn: dashboardApi.get,
  })
}

export function useCourses() {
  return useQuery({
    queryKey: ['courses'],
    queryFn: coursesApi.list,
  })
}

export function useCourseDetail(courseCode: string) {
  return useQuery({
    queryKey: ['courses', courseCode],
    queryFn: () => coursesApi.detail(courseCode),
    enabled: !!courseCode,
  })
}

export function useWeekDetail(courseCode: string, week: number) {
  return useQuery({
    queryKey: ['courses', courseCode, 'weeks', week],
    queryFn: () => coursesApi.week(courseCode, week),
    enabled: !!courseCode && week > 0,
  })
}

export function usePendingReviews() {
  return useQuery({
    queryKey: ['review-items', 'pending'],
    queryFn: () => reviewApi.list('pending'),
  })
}

export function useReviewItems(status: string) {
  return useQuery({
    queryKey: ['review-items', status],
    queryFn: () => reviewApi.list(status),
  })
}

export function useReviewItem(reviewId: string) {
  return useQuery({
    queryKey: ['review-items', 'detail', reviewId],
    queryFn: () => reviewApi.get(reviewId),
    enabled: !!reviewId,
  })
}

export function useResolveReview() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ reviewId, resolution }: { reviewId: string; resolution: Record<string, unknown> }) =>
      reviewApi.resolve(reviewId, resolution),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['review-items'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}

export function useDismissReview() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (reviewId: string) => reviewApi.dismiss(reviewId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['review-items'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}

export function useUpload() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => uploadApi.upload(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      queryClient.invalidateQueries({ queryKey: ['courses'] })
    },
  })
}

export function useAskQuestion() {
  return useMutation({
    mutationFn: (request: QARequest) => qaApi.ask(request),
  })
}

export function useSettings() {
  return useQuery({
    queryKey: ['settings'],
    queryFn: settingsApi.get,
  })
}

export function useUpdateSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (updates: SettingsUpdate) => settingsApi.update(updates),
    onSuccess: (data) => {
      queryClient.setQueryData(['settings'], data)
    },
  })
}

export function useStudyDue(courseCode?: string, week?: number, limit = 20) {
  return useQuery({
    queryKey: ['study', 'due', courseCode, week, limit],
    queryFn: () => studyApi.due(courseCode, week, limit),
  })
}

export function useStudyStats(courseCode?: string, week?: number) {
  return useQuery({
    queryKey: ['study', 'stats', courseCode, week],
    queryFn: () => studyApi.stats(courseCode, week),
  })
}

export function useRecordReview() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: ReviewRequest) => studyApi.review(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['study'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}

export function useFlashcards(courseCode: string, week?: number) {
  return useQuery({
    queryKey: ['assets', 'flashcards', courseCode, week],
    queryFn: () => assetsApi.flashcards(courseCode, week),
    enabled: !!courseCode,
  })
}

export function useQuizQuestions(courseCode: string, week?: number) {
  return useQuery({
    queryKey: ['assets', 'quiz', courseCode, week],
    queryFn: () => assetsApi.quiz(courseCode, week),
    enabled: !!courseCode,
  })
}
