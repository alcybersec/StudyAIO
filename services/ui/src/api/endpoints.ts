import { api } from './client'
import type {
  AnalyticsOverview,
  Assessment,
  BatchUploadResponse,
  ChatMessage,
  ChatSession,
  CourseDetail,
  CourseDocument,
  CourseListItem,
  CreateSessionRequest,
  DailyPlan,
  DashboardData,
  Deadline,
  DeadlineUpdate,
  Exam,
  ExamProgress,
  ExamReadinessData,
  Flashcard,
  HeatmapDay,
  MasteryWeek,
  PipelineRun,
  QARequest,
  QAResponse,
  QuizAttemptRequest,
  QuizQuestion,
  RetentionPoint,
  ReviewItem,
  ReviewRequest,
  ReviewResponse,
  SendMessageResponse,
  Settings,
  SettingsUpdate,
  StreakInfo,
  StudyHistoryDay,
  StudyStats,
  SummaryData,
  TimedPlanRequest,
  TimedSessionPlan,
  UploadResult,
  WeakTopic,
  WeekDetail,
} from '../types'

export const dashboardApi = {
  get: () => api.get<DashboardData>('/dashboard'),
}

export const coursesApi = {
  list: () => api.get<CourseListItem[]>('/courses'),
  detail: (courseCode: string) => api.get<CourseDetail>(`/courses/${courseCode}`),
  week: (courseCode: string, week: number) =>
    api.get<WeekDetail>(`/courses/${courseCode}/weeks/${week}`),
}

export const summariesApi = {
  get: (summaryId: string) => api.get<SummaryData>(`/summaries/${summaryId}`),
}

export const reviewApi = {
  list: (status = 'pending') => api.get<ReviewItem[]>(`/review-items?status=${status}`),
  get: (reviewId: string) => api.get<ReviewItem>(`/review-items/${reviewId}`),
  resolve: (reviewId: string, resolution: Record<string, unknown>) =>
    api.post<ReviewItem>(`/review-items/${reviewId}/resolve`, { resolution }),
  dismiss: (reviewId: string) => api.post<ReviewItem>(`/review-items/${reviewId}/dismiss`),
}

export const uploadApi = {
  upload: (file: File) => api.upload<UploadResult>('/uploads', file),
  batchUpload: (files: File[]) => api.uploadMany<BatchUploadResponse>('/uploads/batch', files),
  status: (artifactId: string) => api.get<PipelineRun[]>(`/uploads/${artifactId}/status`),
  retry: (artifactId: string) => api.post<{ artifact_id: string; status: string; retrying_from_stage: string }>(`/uploads/${artifactId}/retry`),
}

export const qaApi = {
  ask: (request: QARequest) => api.post<QAResponse>('/qa/ask', request),
}

export const settingsApi = {
  get: () => api.get<Settings>('/settings'),
  update: (updates: SettingsUpdate) => api.put<Settings>('/settings', updates),
}

export const examsApi = {
  list: (courseCode?: string, status?: string) => {
    const params = new URLSearchParams()
    if (courseCode) params.set('course_code', courseCode)
    if (status) params.set('status', status)
    return api.get<Exam[]>(`/exams?${params}`)
  },
  detail: (examId: string) => api.get<ExamProgress>(`/exams/${examId}`),
  create: (data: {
    course_code: string
    title: string
    exam_date: string
    weeks_scope: number[]
    target_mastery_pct?: number
  }) => api.post<Exam>('/exams', data),
  update: (examId: string, data: Partial<Exam>) =>
    api.put<Exam>(`/exams/${examId}`, data),
  delete: (examId: string) => api.delete(`/exams/${examId}`),
  schedule: (examId: string, days = 7) =>
    api.get<DailyPlan[]>(`/exams/${examId}/schedule?days=${days}`),
  today: (examId: string) => api.get<DailyPlan>(`/exams/${examId}/today`),
  weakTopics: (examId: string) => api.get<WeakTopic[]>(`/exams/${examId}/weak-topics`),
  recordSession: (examId: string, data: {
    cards_reviewed: number
    quiz_questions_answered: number
    quiz_correct: number
    duration_seconds: number
  }) => api.post(`/exams/${examId}/sessions`, data),
  history: (examId: string, days = 30) =>
    api.get<StudyHistoryDay[]>(`/exams/${examId}/history?days=${days}`),
}

export const studyApi = {
  due: (courseCode?: string, week?: number, limit = 20) => {
    const params = new URLSearchParams()
    if (courseCode) params.set('course_code', courseCode)
    if (week !== undefined) params.set('week', String(week))
    params.set('limit', String(limit))
    return api.get<Flashcard[]>(`/study/due?${params}`)
  },
  review: (request: ReviewRequest) =>
    api.post<ReviewResponse>('/study/review', request),
  stats: (courseCode?: string, week?: number) => {
    const params = new URLSearchParams()
    if (courseCode) params.set('course_code', courseCode)
    if (week !== undefined) params.set('week', String(week))
    return api.get<StudyStats>(`/study/stats?${params}`)
  },
  timedPlan: (request: TimedPlanRequest) =>
    api.post<TimedSessionPlan>('/study/timed-plan', request),
  quizAttempt: (request: QuizAttemptRequest) =>
    api.post('/study/quiz-attempt', request),
  streak: (courseId?: string) => {
    const params = new URLSearchParams()
    if (courseId) params.set('course_id', courseId)
    return api.get<StreakInfo>(`/study/streak?${params}`)
  },
}

export const exportApi = {
  obsidianVaultUrl: (courseCode: string, weeks?: number[]) => {
    const params = new URLSearchParams()
    if (weeks && weeks.length > 0) params.set('weeks', weeks.join(','))
    return api.downloadUrl(`/exports/obsidian/${courseCode}?${params}`)
  },
}

export const assetsApi = {
  flashcards: (courseCode: string, week?: number) => {
    const params = new URLSearchParams({ course_code: courseCode })
    if (week !== undefined) params.set('week', String(week))
    return api.get<Flashcard[]>(`/assets/flashcards?${params}`)
  },
  quiz: (courseCode: string, week?: number) => {
    const params = new URLSearchParams({ course_code: courseCode })
    if (week !== undefined) params.set('week', String(week))
    return api.get<QuizQuestion[]>(`/assets/quiz?${params}`)
  },
}

export const analyticsApi = {
  overview: () => api.get<AnalyticsOverview>('/analytics/overview'),
  heatmap: (days = 90) => api.get<{ days: HeatmapDay[] }>(`/analytics/heatmap?days=${days}`),
  retention: (courseCode?: string) => {
    const params = new URLSearchParams()
    if (courseCode) params.set('course_code', courseCode)
    return api.get<{ points: RetentionPoint[] }>(`/analytics/retention?${params}`)
  },
  mastery: (courseCode?: string) => {
    const params = new URLSearchParams()
    if (courseCode) params.set('course_code', courseCode)
    return api.get<{ weeks: MasteryWeek[] }>(`/analytics/mastery?${params}`)
  },
  readiness: (examId: string) => api.get<ExamReadinessData>(`/analytics/readiness/${examId}`),
}

export const chatApi = {
  createSession: (data: CreateSessionRequest = {}) =>
    api.post<ChatSession>('/chat/sessions', data),
  listSessions: (limit = 50) =>
    api.get<{ sessions: ChatSession[] }>(`/chat/sessions?limit=${limit}`),
  getMessages: (sessionId: string, limit = 100, offset = 0) =>
    api.get<{ messages: ChatMessage[] }>(`/chat/sessions/${sessionId}/messages?limit=${limit}&offset=${offset}`),
  sendMessage: (sessionId: string, content: string) =>
    api.post<SendMessageResponse>(`/chat/sessions/${sessionId}/messages`, { content }),
  deleteSession: (sessionId: string) =>
    api.delete(`/chat/sessions/${sessionId}`),
}

export const gamificationApi = {
  getXP: () =>
    api.get<import('../types').XPSummary>('/gamification/xp'),
  getAchievements: () =>
    api.get<import('../types').AchievementsList>('/gamification/achievements'),
  getChallenges: () =>
    api.get<import('../types').DailyChallengeData>('/gamification/challenges'),
  getLeaderboard: () =>
    api.get<import('../types').Leaderboard>('/gamification/leaderboard'),
  getUnnotified: () =>
    api.get<import('../types').UnnotifiedAchievement[]>('/gamification/achievements/unnotified'),
  markNotified: (ids: string[]) =>
    api.post('/gamification/achievements/mark-notified', { user_achievement_ids: ids }),
}

export const conceptsApi = {
  graph: (courseCode?: string) =>
    api.get<import('../types').ConceptGraph>(
      `/concepts/graph${courseCode ? `?course_code=${courseCode}` : ''}`
    ),
  list: (courseCode?: string, search?: string) => {
    const params = new URLSearchParams()
    if (courseCode) params.set('course_code', courseCode)
    if (search) params.set('search', search)
    const qs = params.toString()
    return api.get<import('../types').ConceptNode[]>(`/concepts${qs ? `?${qs}` : ''}`)
  },
  detail: (conceptId: string) =>
    api.get<import('../types').ConceptDetail>(`/concepts/${conceptId}`),
  related: (conceptId: string) =>
    api.get<import('../types').SimilarConcept[]>(`/concepts/${conceptId}/related`),
  extract: (artifactId: string) =>
    api.post<import('../types').ConceptExtractionResult>(`/concepts/extract/${artifactId}`),
}

export const courseopsApi = {
  uploadDocument: async (file: File, courseCode: string, documentType: string) => {
    const formData = new FormData()
    formData.append('file', file)
    const params = new URLSearchParams({ course_code: courseCode, document_type: documentType })
    const response = await fetch(`/api/courseops/documents?${params}`, {
      method: 'POST',
      body: formData,
    })
    if (!response.ok) {
      const body = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(body.detail || response.statusText)
    }
    return response.json() as Promise<CourseDocument>
  },
  listDocuments: (courseCode: string) =>
    api.get<CourseDocument[]>(`/courseops/documents?course_code=${courseCode}`),
  getDocument: (documentId: string) =>
    api.get<CourseDocument>(`/courseops/documents/${documentId}`),
  listAssessments: (courseCode: string) =>
    api.get<Assessment[]>(`/courseops/assessments?course_code=${courseCode}`),
  listDeadlines: (courseCode: string, upcoming = false) =>
    api.get<Deadline[]>(`/courseops/deadlines?course_code=${courseCode}&upcoming=${upcoming}`),
  updateDeadline: (deadlineId: string, data: DeadlineUpdate) =>
    api.put<Deadline>(`/courseops/deadlines/${deadlineId}`, data),
  deleteDeadline: (deadlineId: string) =>
    api.delete(`/courseops/deadlines/${deadlineId}`),
  createExamFromDeadline: (deadlineId: string) =>
    api.post<{ exam_id: string; title: string; exam_date: string; status: string }>(
      `/courseops/deadlines/${deadlineId}/create-exam`
    ),
  calendarUrl: (courseCode: string) =>
    api.downloadUrl(`/courseops/export/calendar/${courseCode}`),
  taskPlanUrl: (courseCode: string) =>
    api.downloadUrl(`/courseops/export/task-plan/${courseCode}`),
}
