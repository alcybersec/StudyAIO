import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { coursesApi, dashboardApi, reviewApi, uploadApi } from '../api/endpoints'

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
