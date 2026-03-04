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
  active_exams: DashboardExamSummary[]
  streak: StreakInfo | null
  upcoming_deadlines: UpcomingDeadline[]
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
  agent_backend: string
  anthropic_api_key: string
  openai_api_key: string
  openai_model: string
  ollama_base_url: string
  ollama_model: string
  embedding_backend: string
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

// ── Exams ───────────────────────────────────────────────────────

export interface Exam {
  id: string
  course_id: string
  title: string
  exam_date: string
  weeks_scope: number[]
  target_mastery_pct: number
  status: string
  created_at: string
  updated_at: string
}

export interface ExamProgress {
  exam_id: string
  title: string
  course_id: string
  exam_date: string
  status: string
  days_remaining: number
  mastery_pct: number
  target_mastery_pct: number
  quiz_accuracy: number
  quiz_total: number
  quiz_correct: number
  flashcard_total: number
  flashcard_mastered: number
  weak_weeks: number[]
  session_count: number
  weeks_scope: number[]
}

export interface WeakTopic {
  week: number
  quiz_accuracy: number | null
  quiz_attempts: number
  avg_ease: number | null
  reasons: string[]
  weakness_score: number
}

export interface DailyPlan {
  date: string
  days_until_exam: number
  priority: string
  card_target: number
  quiz_target: number
  focus_weeks: number[]
}

export interface StreakInfo {
  current_streak: number
  longest_streak: number
  last_study_date: string | null
}

export interface QuizAttemptRequest {
  quiz_question_id: string
  selected_answer: string
  is_correct: boolean
  exam_id?: string
  time_spent_ms?: number
}

export interface DashboardExamSummary {
  exam_id: string
  title: string
  course_id: string
  course_code: string
  exam_date: string
  days_remaining: number
  mastery_pct: number
  target_mastery_pct: number
}

export interface StudyHistoryDay {
  date: string
  cards_reviewed: number
  quiz_answered: number
  quiz_correct: number
  duration_seconds: number
  session_count: number
}

// ── Timed Study ─────────────────────────────────────────────────

export interface TimedPlanRequest {
  minutes: number
  course_code?: string
  exam_id?: string
}

export interface TimedSessionPlan {
  total_minutes: number
  card_ids: string[]
  quiz_ids: string[]
  estimated_card_minutes: number
  estimated_quiz_minutes: number
  course_code: string | null
  exam_id: string | null
}

// ── Batch Upload ────────────────────────────────────────────────

export interface BatchUploadFileResult {
  filename: string
  status: 'processing' | 'duplicate' | 'error'
  artifact_id: string | null
  error: string | null
}

export interface BatchUploadResponse {
  total: number
  succeeded: number
  duplicates: number
  failed: number
  results: BatchUploadFileResult[]
}

// ── Study / SRS ──────────────────────────────────────────────────

export interface StudyStats {
  total: number
  due_today: number
  mastered: number
  learning: number
  new: number
}

// ── CourseOps ──────────────────────────────────────────────────

export interface CourseDocument {
  id: string
  course_id: string
  document_type: string
  title: string | null
  original_filename: string
  file_type: string
  sha256: string
  file_size_bytes: number
  status: string
  created_at: string
  updated_at: string
}

export interface Assessment {
  id: string
  course_id: string
  source_document_id: string | null
  title: string
  assessment_type: string
  weight_pct: number | null
  description: string | null
  weeks_relevant: number[] | null
  created_at: string
  updated_at: string
}

export interface Deadline {
  id: string
  course_id: string
  assessment_id: string | null
  source_document_id: string | null
  title: string
  due_date: string
  deadline_type: string
  description: string | null
  is_confirmed: boolean
  created_at: string
  updated_at: string
}

export interface DeadlineUpdate {
  title?: string
  due_date?: string
  deadline_type?: string
  description?: string
  is_confirmed?: boolean
}

export interface UpcomingDeadline {
  id: string
  title: string
  due_date: string
  deadline_type: string
  course_code: string
  is_confirmed: boolean
}

// ── Auth ──────────────────────────────────────────────────────────

export interface AuthConfig {
  self_hosted: boolean
  registration_enabled: boolean
  oauth_providers: string[]
}

export interface AuthUser {
  id: string
  email: string
  username: string
  role: string
  tier: string
  is_active: boolean
  email_verified: boolean
  mfa_enabled: boolean
  avatar_url: string | null
  last_login_at: string | null
  created_at: string
}

export interface LoginRequest {
  email: string
  password: string
  totp_code?: string
}

export interface RegisterRequest {
  email: string
  username: string
  password: string
}

export interface ChangePasswordRequest {
  old_password: string
  new_password: string
}

export interface ForgotPasswordRequest {
  email: string
}

export interface ResetPasswordRequest {
  token: string
  new_password: string
}

export interface UpdateProfileRequest {
  username?: string
  avatar_url?: string
}

export interface MFASetupResponse {
  secret: string
  qr_code_base64: string
  provisioning_uri: string
}

export interface MFAVerifyRequest {
  totp_code: string
  secret: string
}

export interface MFAVerifyResponse {
  detail: string
  backup_codes: string[]
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
