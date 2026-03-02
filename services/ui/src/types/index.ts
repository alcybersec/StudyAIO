export interface Course {
  id: string
  code: string
  name: string | null
  term: string | null
  created_at: string
  updated_at: string
}

export interface CourseListItem extends Course {
  weeks_covered: number
  total_artifacts: number
  last_updated: string | null
}

export interface WeekSummaryRow {
  week: number
  titles: string[]
  artifact_count: number
  summary_status: string
  summary_id: string | null
  flashcard_count: number
  quiz_count: number
}

export interface CourseDetail {
  course: Course
  weeks: WeekSummaryRow[]
}

export interface Artifact {
  id: string
  course_id: string | null
  week: number | null
  title: string | null
  original_filename: string
  file_type: string
  sha256: string
  file_size_bytes: number
  status: string
  created_at: string
}

export interface SummaryData {
  id: string
  course_id: string
  week: number
  content_md: string
  version: number
  source_artifacts: string[] | null
  created_at: string
  updated_at: string
}

export interface ReviewItem {
  id: string
  review_type: string
  entity_type: string
  entity_id: string
  payload_json: Record<string, unknown>
  suggested_values: Record<string, unknown>
  status: string
  resolution_json: Record<string, unknown> | null
  created_at: string
  resolved_at: string | null
}

export interface ActivityItem {
  pipeline_run_id: string
  artifact_id: string
  filename: string | null
  stage: string
  status: string
  started_at: string | null
  completed_at: string | null
  duration_ms: number | null
}

export interface CourseDueCount {
  course_code: string
  due_count: number
}

export interface DashboardStudyStats {
  total: number
  due_today: number
  mastered: number
  learning: number
  new: number
  per_course: CourseDueCount[]
}

export interface DashboardData {
  pending_review_count: number
  recent_activity: ActivityItem[]
  courses: CourseListItem[]
  study_stats: DashboardStudyStats | null
}

export interface UploadResult {
  artifact_id: string
  filename: string
  status: string
  pipeline_task_id: string | null
}

export interface PipelineEvent {
  artifact_id: string
  stage: string
  status: string
  message: string | null
}

export interface PipelineRun {
  id: string
  artifact_id: string
  stage: string
  status: string
  error_message: string | null
  started_at: string
  completed_at: string | null
  duration_ms: number | null
}

export interface WeekDetail {
  course: Course
  week: number
  summary: SummaryData | null
  artifacts: Artifact[]
}

export interface QARequest {
  question: string
  course_code?: string
  week?: number
  top_k?: number
}

export interface Citation {
  ref: number
  chunk_id: string
  text_snippet: string
  course_code: string
  week: number
  page_ref: number
  artifact_id: string
}

export interface QAResponse {
  answer: string
  citations: Citation[]
  chunks_searched: number
}

export interface QAExchange {
  question: string
  response: QAResponse
  timestamp: string
}

export interface Settings {
  claude_code_path: string
  claude_model: string
  classification_confidence_threshold: number
  flashcard_count_per_week: number
  quiz_question_count_per_week: number
  chunk_size_tokens: number
  chunk_overlap_tokens: number
}

export type SettingsUpdate = Partial<Settings>

export interface Flashcard {
  id: string
  course_id: string
  week: number
  front: string
  back: string
  tags: string[]
  source_artifact_id: string
  source_page_ref: number
  generation_version: number
  created_at: string
}

export interface QuizQuestion {
  id: string
  course_id: string
  week: number
  question_type: 'multiple_choice' | 'short_answer'
  question: string
  options_json: string[] | null
  correct_answer: string
  explanation: string
  source_artifact_id: string
  source_page_ref: number
  generation_version: number
  created_at: string
}

// ── Study / SRS ──────────────────────────────────────────────────

export interface StudyStats {
  total: number
  due_today: number
  mastered: number
  learning: number
  new: number
}

export interface ReviewRequest {
  flashcard_id: string
  quality: number
}

export interface ReviewResponse {
  id: string
  flashcard_id: string
  ease_factor: number
  interval_days: number
  repetition_count: number
  next_review_at: string
  last_reviewed_at: string | null
}
