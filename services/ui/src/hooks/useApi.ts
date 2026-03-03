import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { assetsApi, coursesApi, dashboardApi, examsApi, qaApi, reviewApi, settingsApi, studyApi, uploadApi } from '../api/endpoints'
import type { QARequest, QuizAttemptRequest, ReviewRequest, SettingsUpdate, TimedPlanRequest } from '../types'

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

export function useExams(courseCode?: string, status?: string) {
  return useQuery({
    queryKey: ['exams', courseCode, status],
    queryFn: () => examsApi.list(courseCode, status),
  })
}

export function useExamDetail(examId: string) {
  return useQuery({
    queryKey: ['exams', 'detail', examId],
    queryFn: () => examsApi.detail(examId),
    enabled: !!examId,
  })
}

export function useExamSchedule(examId: string, days = 7) {
  return useQuery({
    queryKey: ['exams', 'schedule', examId, days],
    queryFn: () => examsApi.schedule(examId, days),
    enabled: !!examId,
  })
}

export function useExamWeakTopics(examId: string) {
  return useQuery({
    queryKey: ['exams', 'weak-topics', examId],
    queryFn: () => examsApi.weakTopics(examId),
    enabled: !!examId,
  })
}

export function useExamHistory(examId: string, days = 30) {
  return useQuery({
    queryKey: ['exams', 'history', examId, days],
    queryFn: () => examsApi.history(examId, days),
    enabled: !!examId,
  })
}

export function useCreateExam() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: {
      course_code: string
      title: string
      exam_date: string
      weeks_scope: number[]
      target_mastery_pct?: number
    }) => examsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['exams'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}

export function useDeleteExam() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (examId: string) => examsApi.delete(examId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['exams'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}

export function useRecordQuizAttempt() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: QuizAttemptRequest) => studyApi.quizAttempt(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['exams'] })
    },
  })
}

export function useStreak(courseId?: string) {
  return useQuery({
    queryKey: ['study', 'streak', courseId],
    queryFn: () => studyApi.streak(courseId),
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

export function useTimedPlan() {
  return useMutation({
    mutationFn: (request: TimedPlanRequest) => studyApi.timedPlan(request),
  })
}

export function useBatchUpload() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (files: File[]) => uploadApi.batchUpload(files),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      queryClient.invalidateQueries({ queryKey: ['courses'] })
    },
  })
}
