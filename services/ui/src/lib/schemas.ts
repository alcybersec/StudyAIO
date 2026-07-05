import { z } from 'zod'

export const examCreateSchema = z.object({
  courseCode: z.string().min(1, 'Select a course'),
  title: z.string().min(1, 'Title is required').max(200, 'Title too long'),
  examDate: z.string().min(1, 'Exam date is required'),
  weeksInput: z.string().min(1, 'Enter at least one week').refine(
    (val) => {
      const weeks = val.split(',').map(s => parseInt(s.trim(), 10)).filter(n => !isNaN(n) && n > 0)
      return weeks.length > 0
    },
    { message: 'Enter valid week numbers (e.g. 1, 2, 3)' }
  ),
  targetMastery: z.number().min(50).max(100),
})

export type ExamCreateFormData = z.infer<typeof examCreateSchema>

export const customResolutionSchema = z.object({
  courseCode: z.string().optional(),
  weekNumber: z.string().optional(),
  title: z.string().optional(),
}).refine(
  (data) => (data.courseCode?.trim() || data.weekNumber?.trim() || data.title?.trim()),
  { message: 'At least one field is required' }
)

export type CustomResolutionFormData = z.infer<typeof customResolutionSchema>

export const deadlineEditSchema = z.object({
  title: z.string().min(1, 'Title is required'),
  dueDate: z.string().min(1, 'Due date is required'),
  deadlineType: z.string().min(1),
  description: z.string().optional(),
})

export type DeadlineEditFormData = z.infer<typeof deadlineEditSchema>

// ── Settings (D9) ──────────────────────────────────────────────

export const AGENT_BACKENDS = ['claude_code', 'anthropic_api', 'openai', 'ollama'] as const
export const EMBEDDING_BACKENDS = ['sentence_transformers', 'openai', 'ollama'] as const

export const aiProviderSettingsSchema = z.object({
  agent_backend: z.enum(AGENT_BACKENDS),
  claude_code_path: z.string().min(1, 'Path is required'),
  claude_model: z.string().min(1, 'Pick a model'),
  claude_cli_credentials: z.string(),
  anthropic_api_key: z
    .string()
    .refine((v) => v === '' || v.startsWith('sk-ant-'), { message: 'Key must start with sk-ant-' }),
  openai_api_key: z
    .string()
    .refine((v) => v === '' || v.startsWith('sk-'), { message: 'Key must start with sk-' }),
  openai_model: z.string(),
  ollama_base_url: z
    .string()
    .refine((v) => v === '' || /^https?:\/\/\S+$/.test(v), { message: 'Must be an http(s) URL' }),
  ollama_model: z.string(),
  embedding_backend: z.enum(EMBEDDING_BACKENDS),
  classification_confidence_threshold: z
    .number({ message: 'Enter a number between 0 and 1' })
    .min(0, 'Must be at least 0')
    .max(1, 'Must be at most 1'),
})

export type AiProviderSettingsFormData = z.infer<typeof aiProviderSettingsSchema>

export const pipelineSettingsSchema = z.object({
  flashcard_count_per_week: z
    .number({ message: 'Enter a number' })
    .int('Whole numbers only')
    .min(1, 'At least 1')
    .max(100, 'At most 100'),
  quiz_question_count_per_week: z
    .number({ message: 'Enter a number' })
    .int('Whole numbers only')
    .min(1, 'At least 1')
    .max(100, 'At most 100'),
  chunk_size_tokens: z
    .number({ message: 'Enter a number' })
    .int('Whole numbers only')
    .min(50, 'At least 50')
    .max(5000, 'At most 5000'),
  chunk_overlap_tokens: z
    .number({ message: 'Enter a number' })
    .int('Whole numbers only')
    .min(0, 'At least 0')
    .max(500, 'At most 500'),
})

export type PipelineSettingsFormData = z.infer<typeof pipelineSettingsSchema>

// ── Auth (D10) ─────────────────────────────────────────────────

export const loginSchema = z.object({
  email: z.string().min(1, 'Email is required').email('Enter a valid email address'),
  password: z.string().min(1, 'Password is required'),
  totp_code: z.string().optional(),
})

export type LoginFormData = z.infer<typeof loginSchema>

export const registerSchema = z
  .object({
    email: z.string().min(1, 'Email is required').email('Enter a valid email address'),
    username: z.string().min(3, 'Username must be at least 3 characters'),
    password: z.string().min(8, 'Password must be at least 8 characters'),
    confirm: z.string(),
  })
  .refine((data) => data.password === data.confirm, {
    message: 'Passwords do not match',
    path: ['confirm'],
  })

export type RegisterFormData = z.infer<typeof registerSchema>

export const forgotPasswordSchema = z.object({
  email: z.string().min(1, 'Email is required').email('Enter a valid email address'),
})

export type ForgotPasswordFormData = z.infer<typeof forgotPasswordSchema>

export const resetPasswordSchema = z
  .object({
    password: z.string().min(8, 'Password must be at least 8 characters'),
    confirm: z.string(),
  })
  .refine((data) => data.password === data.confirm, {
    message: 'Passwords do not match',
    path: ['confirm'],
  })

export type ResetPasswordFormData = z.infer<typeof resetPasswordSchema>
