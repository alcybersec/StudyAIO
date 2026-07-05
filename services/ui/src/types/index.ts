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
  gamification: DashboardGamificationSummary | null
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
  /** Client-side receipt stamp (ms epoch), added by usePipelineEvents for stage timings. */
  receivedAt?: number
}

export interface ReclassifyResponse {
  artifact_id: string
  course_code: string
  week: number
  summaries_enqueued: number
}

export interface RetryResponse {
  artifact_id: string
  status: string
  retrying_from_stage: string
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

export interface Settings {
  claude_code_path: string
  claude_model: string
  agent_backend: string
  anthropic_api_key: string
  claude_cli_credentials: string
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
  dashboard_layout: Record<string, unknown> | null
}

export interface TestAIResponse {
  status: string
  backend: string
  message: string
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
  demo_enabled: boolean
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

// ── Chat ──────────────────────────────────────────────────────

export interface ChatSession {
  id: string
  title: string
  course_id: string | null
  message_count: number
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  id: string
  session_id: string
  role: 'user' | 'assistant'
  content: string
  citations_json: Record<string, unknown>[] | null
  created_at: string
}

export interface CreateSessionRequest {
  title?: string
  course_code?: string
}

export interface SendMessageRequest {
  content: string
  course_code?: string | null
  week?: number | null
}

/** Per-message RAG scope (chips on the Ask composer). */
export interface MessageScope {
  courseCode?: string | null
  week?: number | null
}

export interface SendMessageResponse {
  user_message: ChatMessage
  assistant_message: ChatMessage
}

// ── Gamification ──────────────────────────────────────────────

export interface XPEvent {
  id: string
  event_type: string
  xp_amount: number
  created_at: string
}

export interface XPSummary {
  total_xp: number
  level: number
  progress_pct: number
  current_threshold: number
  next_threshold: number | null
  recent_events: XPEvent[]
}

export interface Achievement {
  id: string
  code: string
  title: string
  description: string
  icon: string
  category: string
  xp_reward: number
  earned: boolean
  earned_at: string | null
}

export interface AchievementsList {
  total: number
  earned: number
  achievements: Achievement[]
}

export interface DailyChallengeData {
  challenge_id: string
  challenge_date: string
  challenge_type: string
  target: number
  description: string
  xp_reward: number
  progress: number
  completed: boolean
  completed_at: string | null
}

export interface LeaderboardEntry {
  user_id: string
  username: string
  total_xp: number
  level: number
  rank: number
}

export interface Leaderboard {
  entries: LeaderboardEntry[]
}

export interface UnnotifiedAchievement {
  user_achievement_id: string
  code: string
  title: string
  description: string
  icon: string
  xp_reward: number
  earned_at: string
}

export interface DashboardGamificationSummary {
  total_xp: number
  level: number
  progress_pct: number
  next_threshold: number | null
  daily_challenge_description: string | null
  daily_challenge_progress: number
  daily_challenge_target: number
  daily_challenge_completed: boolean
  unnotified_achievement_count: number
}

// ── Knowledge Graph / Concepts ──────────────────────────────────

export interface ConceptNode {
  id: string
  name: string
  description: string
  category: string
  mention_count: number
  source_weeks: number[]
  course_id: string
  created_at: string | null
}

export interface ConceptEdge {
  id: string
  source: string
  target: string
  relation_type: string
  confidence: number
}

export interface ConceptGraph {
  nodes: ConceptNode[]
  edges: ConceptEdge[]
}

export interface ConceptRelationItem {
  id: string
  concept_id: string
  concept_name: string
  relation_type: string
  confidence: number
}

export interface ConceptDetail {
  id: string
  name: string
  description: string
  category: string
  mention_count: number
  source_artifact_ids: string[]
  source_weeks: number[]
  course_id: string
  outgoing_relations: ConceptRelationItem[]
  incoming_relations: ConceptRelationItem[]
  created_at: string | null
  updated_at: string | null
}

export interface SimilarConcept {
  id: string
  name: string
  description: string
  category: string
  course_id: string
  similarity: number
}

export interface ConceptExtractionResult {
  artifact_id: string
  concept_count: number
  relation_count: number
}

// ── Billing ──────────────────────────────────────────────────

export interface Subscription {
  plan: string
  status: string
  current_period_start: string | null
  current_period_end: string | null
  cancel_at_period_end: boolean
}

export interface UsageSummary {
  ai_calls_today: number
  ai_calls_limit: number | null
  uploads_this_month: number
  uploads_limit: number | null
  courses_count: number
  courses_limit: number | null
}

export interface BillingOverview {
  subscription: Subscription
  usage: UsageSummary
}

export interface CheckoutRequest {
  success_url: string
  cancel_url: string
}

export interface CheckoutResponse {
  checkout_url: string
}

export interface PortalResponse {
  portal_url: string
}

export interface QuotaError {
  detail: string
  resource: string
  limit: number
  period: string
}

// ── Analytics ──────────────────────────────────────────────────

export interface AnalyticsOverview {
  total_study_hours: number
  total_cards_reviewed: number
  total_sessions: number
  mastery_pct: number
  total_flashcards: number
  mastered_flashcards: number
  active_courses: number
}

export interface HeatmapDay {
  date: string
  minutes: number
  cards: number
  sessions: number
}

export interface RetentionPoint {
  interval_bucket: number
  retention_pct: number
  card_count: number
}

export interface MasteryWeek {
  course_code: string
  week: number
  total: number
  mastered: number
  learning: number
  new: number
  mastery_pct: number
}

// Notification types
export interface NotificationPreferenceItem {
  channel: string
  event_type: string
  enabled: boolean
}

export interface NotificationPreferencesResponse {
  preferences: NotificationPreferenceItem[]
}

export interface TelegramLinkResponse {
  link_token: string
  bot_username: string
  deep_link: string
}

export interface TelegramStatusResponse {
  linked: boolean
  username: string | null
  verified: boolean
}

export interface TestNotificationResponse {
  success: boolean
  channel: string
  message: string
}

// ── Admin ──────────────────────────────────────────────────────

export interface AdminUser {
  id: string
  email: string
  username: string | null
  role: string
  tier: string
  is_active: boolean
  created_at: string | null
  last_login_at: string | null
}

export interface AdminUserList {
  users: AdminUser[]
  total: number
  offset: number
  limit: number
}

export interface AdminUserUpdate {
  role?: string
  tier?: string
  is_active?: boolean
}

export interface SystemMetrics {
  total_users: number
  total_artifacts: number
  total_courses: number
  pipeline_runs_24h: number
  total_storage_bytes: number
  total_storage_mb: number
}

// ── Admin User Detail ─────────────────────────────────────────

export interface AdminUserProfile {
  id: string
  email: string
  username: string | null
  role: string
  tier: string
  is_active: boolean
  email_verified: boolean
  mfa_enabled: boolean
  avatar_url: string | null
  last_login_at: string | null
  created_at: string | null
}

export interface AdminSubscriptionSection {
  plan: string
  status: string
  current_period_start: string | null
  current_period_end: string | null
  cancel_at_period_end: boolean
}

export interface AdminStorageSection {
  total_bytes: number
  total_mb: number
  total_files: number
  status_breakdown: Record<string, number>
}

export interface AdminUsagePeriod {
  ai_calls: number
  tokens_input: number
  tokens_output: number
  uploads: number
}

export interface AdminUsageSection {
  today: AdminUsagePeriod
  last_30_days: AdminUsagePeriod
}

export interface AdminPipelineStage {
  stage: string
  total: number
  success: number
  failed: number
}

export interface AdminPipelineFailure {
  stage: string
  error_message: string | null
  started_at: string | null
}

export interface AdminPipelineSection {
  total_runs: number
  success_count: number
  failed_count: number
  avg_duration_ms: number
  stages: AdminPipelineStage[]
  recent_failures: AdminPipelineFailure[]
}

export interface AdminStudySection {
  total_sessions: number
  cards_reviewed: number
  quiz_questions_answered: number
  quiz_correct: number
  quiz_accuracy_pct: number
  total_study_hours: number
}

export interface AdminCourseBreakdown {
  code: string
  name: string | null
  artifact_count: number
}

export interface AdminContentSection {
  courses_count: number
  artifacts_count: number
  exams_count: number
  per_course: AdminCourseBreakdown[]
}

export interface AdminGamificationSection {
  total_xp: number
  level: number
  achievements_count: number
}

export interface AdminChatSection {
  total_sessions: number
  total_messages: number
  total_tokens: number
}

export interface AdminUserDetail {
  profile: AdminUserProfile
  subscription: AdminSubscriptionSection | null
  storage: AdminStorageSection | null
  usage: AdminUsageSection | null
  pipeline: AdminPipelineSection | null
  study: AdminStudySection | null
  content: AdminContentSection | null
  gamification: AdminGamificationSection | null
  chat: AdminChatSection | null
}

// ── Calendar Sync ──────────────────────────────────────────────

export interface CalendarSyncInfo {
  id: string
  google_calendar_id: string
  sync_direction: string
  last_synced_at: string | null
  event_count: number
}

export interface CalendarSyncStatusResponse {
  calendars: CalendarSyncInfo[]
}

export interface CalendarConnectResponse {
  sync_id: string
  calendar_id: string
}

export interface CalendarSyncResult {
  pushed: number
  pulled: number
}

export interface ExamReadinessData {
  exam_id: string
  title: string
  readiness_score: number
  mastery_score: number
  quiz_score: number
  consistency_score: number
  days_remaining: number
  weak_weeks: number[]
  flashcard_total: number
  flashcard_mastered: number
  quiz_total: number
  quiz_correct: number
  study_days_last_week: number
}

// ── Readiness drill-down (GET /api/exams/{id}/readiness) ───────

export interface ReadinessTopic {
  topic: string
  week: number
  accuracy: number | null
  weight: number
  card_count: number
}

export interface ReadinessDetail {
  exam_id: string
  title: string
  overall: number
  topics: ReadinessTopic[]
}
