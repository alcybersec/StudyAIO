import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { analyticsApi, artifactsApi, assetsApi, chatApi, conceptsApi, courseopsApi, coursesApi, dashboardApi, examsApi, gamificationApi, reviewApi, settingsApi, studyApi, uploadApi } from '../api/endpoints'
import { adminApi } from '../api/admin'
import type { AdminUserUpdate, CreateSessionRequest, DashboardData, DeadlineUpdate, QuizAttemptRequest, ReviewRequest, SettingsUpdate, TimedPlanRequest } from '../types'

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
      queryClient.invalidateQueries({ queryKey: ['gamification'] })
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
      queryClient.invalidateQueries({ queryKey: ['gamification'] })
    },
  })
}

export function useStudyPlan() {
  return useQuery({
    queryKey: ['study', 'plan'],
    queryFn: studyApi.getPlan,
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

// ── CourseOps ──────────────────────────────────────────────────

export function useCourseDocuments(courseCode: string) {
  return useQuery({
    queryKey: ['courseops', 'documents', courseCode],
    queryFn: () => courseopsApi.listDocuments(courseCode),
    enabled: !!courseCode,
  })
}

export function useAssessments(courseCode: string) {
  return useQuery({
    queryKey: ['courseops', 'assessments', courseCode],
    queryFn: () => courseopsApi.listAssessments(courseCode),
    enabled: !!courseCode,
  })
}

export function useDeadlines(courseCode: string, upcoming = false) {
  return useQuery({
    queryKey: ['courseops', 'deadlines', courseCode, upcoming],
    queryFn: () => courseopsApi.listDeadlines(courseCode, upcoming),
    enabled: !!courseCode,
  })
}

export function useUploadCourseDocument() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ file, courseCode, documentType }: { file: File; courseCode: string; documentType: string }) =>
      courseopsApi.uploadDocument(file, courseCode, documentType),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['courseops', 'documents', variables.courseCode] })
    },
  })
}

export function useUpdateDeadline() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ deadlineId, data }: { deadlineId: string; data: DeadlineUpdate }) =>
      courseopsApi.updateDeadline(deadlineId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['courseops'] })
    },
  })
}

export function useDeleteDeadline() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (deadlineId: string) => courseopsApi.deleteDeadline(deadlineId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['courseops'] })
    },
  })
}

export function useCreateExamFromDeadline() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (deadlineId: string) => courseopsApi.createExamFromDeadline(deadlineId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['courseops'] })
      queryClient.invalidateQueries({ queryKey: ['exams'] })
    },
  })
}

// ── Knowledge Graph / Concepts ──────────────────────────────────

export function useConceptGraph(courseCode?: string) {
  return useQuery({
    queryKey: ['concepts', 'graph', courseCode],
    queryFn: () => conceptsApi.graph(courseCode),
  })
}

export function useConceptList(courseCode?: string, search?: string) {
  return useQuery({
    queryKey: ['concepts', 'list', courseCode, search],
    queryFn: () => conceptsApi.list(courseCode, search),
  })
}

export function useConceptDetail(conceptId: string) {
  return useQuery({
    queryKey: ['concepts', 'detail', conceptId],
    queryFn: () => conceptsApi.detail(conceptId),
    enabled: !!conceptId,
  })
}

export function useRelatedConcepts(conceptId: string) {
  return useQuery({
    queryKey: ['concepts', 'related', conceptId],
    queryFn: () => conceptsApi.related(conceptId),
    enabled: !!conceptId,
  })
}

export function useExtractConcepts() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (artifactId: string) => conceptsApi.extract(artifactId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['concepts'] })
    },
  })
}

// ── Analytics ──────────────────────────────────────────────────

export function useAnalyticsOverview() {
  return useQuery({
    queryKey: ['analytics', 'overview'],
    queryFn: analyticsApi.overview,
  })
}

export function useAnalyticsHeatmap(days = 90) {
  return useQuery({
    queryKey: ['analytics', 'heatmap', days],
    queryFn: () => analyticsApi.heatmap(days),
  })
}

export function useAnalyticsRetention(courseCode?: string) {
  return useQuery({
    queryKey: ['analytics', 'retention', courseCode],
    queryFn: () => analyticsApi.retention(courseCode),
  })
}

export function useAnalyticsMastery(courseCode?: string) {
  return useQuery({
    queryKey: ['analytics', 'mastery', courseCode],
    queryFn: () => analyticsApi.mastery(courseCode),
  })
}

export function useAnalyticsReadiness(examId: string) {
  return useQuery({
    queryKey: ['analytics', 'readiness', examId],
    queryFn: () => analyticsApi.readiness(examId),
    enabled: !!examId,
  })
}

export function useExamReadiness(examId: string) {
  return useQuery({
    queryKey: ['exams', examId, 'readiness'],
    queryFn: () => examsApi.getReadiness(examId),
    enabled: !!examId,
  })
}

// ── Chat ──────────────────────────────────────────────────────

export function useChatSessions() {
  return useQuery({
    queryKey: ['chat', 'sessions'],
    queryFn: () => chatApi.listSessions(),
  })
}

export function useChatMessages(sessionId: string) {
  return useQuery({
    queryKey: ['chat', 'messages', sessionId],
    queryFn: () => chatApi.getMessages(sessionId),
    enabled: !!sessionId,
  })
}

export function useCreateChatSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (data: CreateSessionRequest = {}) => chatApi.createSession(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chat', 'sessions'] })
    },
  })
}

export function useSendChatMessage() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ sessionId, content }: { sessionId: string; content: string }) =>
      chatApi.sendMessage(sessionId, content),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ['chat', 'messages', variables.sessionId] })
      queryClient.invalidateQueries({ queryKey: ['chat', 'sessions'] })
    },
  })
}

export function useDeleteChatSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (sessionId: string) => chatApi.deleteSession(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chat', 'sessions'] })
    },
  })
}

// ── Gamification ──────────────────────────────────────────────

export function useXPSummary() {
  return useQuery({
    queryKey: ['gamification', 'xp'],
    queryFn: gamificationApi.getXP,
  })
}

export function useAchievements() {
  return useQuery({
    queryKey: ['gamification', 'achievements'],
    queryFn: gamificationApi.getAchievements,
  })
}

export function useDailyChallenge() {
  return useQuery({
    queryKey: ['gamification', 'challenges'],
    queryFn: gamificationApi.getChallenges,
  })
}

export function useLeaderboard() {
  return useQuery({
    queryKey: ['gamification', 'leaderboard'],
    queryFn: gamificationApi.getLeaderboard,
  })
}

export function useUnnotifiedAchievements() {
  return useQuery({
    queryKey: ['gamification', 'unnotified'],
    queryFn: gamificationApi.getUnnotified,
    refetchInterval: 30000, // poll every 30s
  })
}

export function useMarkAchievementsNotified() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (ids: string[]) => gamificationApi.markNotified(ids),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['gamification', 'unnotified'] })
    },
  })
}

// ── Admin ──────────────────────────────────────────────────────

export function useAdminUsers(params?: {
  role?: string
  tier?: string
  is_active?: boolean
  offset?: number
  limit?: number
}) {
  return useQuery({
    queryKey: ['admin', 'users', params],
    queryFn: () => adminApi.listUsers(params),
  })
}

export function useUpdateAdminUser() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ userId, data }: { userId: string; data: AdminUserUpdate }) =>
      adminApi.updateUser(userId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] })
    },
  })
}

export function useSystemMetrics() {
  return useQuery({
    queryKey: ['admin', 'metrics'],
    queryFn: adminApi.getMetrics,
  })
}

export function useAdminUserDetail(userId: string | undefined) {
  return useQuery({
    queryKey: ['admin', 'users', userId, 'details'],
    queryFn: () => adminApi.getUserDetails(userId!),
    enabled: !!userId,
  })
}

export function useReclassifyArtifact() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ artifactId, courseCode, week }: { artifactId: string; courseCode: string; week: number }) =>
      artifactsApi.reclassify(artifactId, { course_code: courseCode, week }),
    onSuccess: () => {
      // Week/course detail queries nest under ['courses', …] — both source and
      // target weeks change, so invalidate the whole course tree + dashboard.
      queryClient.invalidateQueries({ queryKey: ['courses'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })
}

export function useRetryPipeline() {
  return useMutation({
    mutationFn: (artifactId: string) => uploadApi.retry(artifactId),
  })
}

// ── Dashboard slices ───────────────────────────────────────────
// Per-widget hooks that share the ['dashboard'] cache entry (one network
// request) while letting each widget own its loading/error/empty state.

export function useDashboardSlice<T>(select: (data: DashboardData) => T) {
  return useQuery({
    queryKey: ['dashboard'],
    queryFn: dashboardApi.get,
    select,
  })
}

export function useDashboardStreak() {
  return useDashboardSlice((d) => d.streak)
}

export function useDashboardExams() {
  return useDashboardSlice((d) => d.active_exams)
}

export function useDashboardGamification() {
  return useDashboardSlice((d) => d.gamification)
}

export function useDashboardStudyStats() {
  return useDashboardSlice((d) => d.study_stats)
}

export function useDashboardDeadlines() {
  return useDashboardSlice((d) => d.upcoming_deadlines)
}

export function useDashboardActivity() {
  return useDashboardSlice((d) => d.recent_activity)
}

export function useDashboardCourses() {
  return useDashboardSlice((d) => d.courses)
}

export function useDashboardPendingReviews() {
  return useDashboardSlice((d) => d.pending_review_count)
}
