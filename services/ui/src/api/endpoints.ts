import { api } from './client'
import type {
  CourseDetail,
  CourseListItem,
  DashboardData,
  PipelineRun,
  QARequest,
  QAResponse,
  ReviewItem,
  SummaryData,
  UploadResult,
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
  status: (artifactId: string) => api.get<PipelineRun[]>(`/uploads/${artifactId}/status`),
}

export const qaApi = {
  ask: (request: QARequest) => api.post<QAResponse>('/qa/ask', request),
}
