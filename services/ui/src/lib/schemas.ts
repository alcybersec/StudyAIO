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

export const deadlineEditSchema = z.object({
  title: z.string().min(1, 'Title is required'),
  dueDate: z.string().min(1, 'Due date is required'),
  deadlineType: z.string().min(1),
  description: z.string().optional(),
})

export type DeadlineEditFormData = z.infer<typeof deadlineEditSchema>

export const deadlineCreateSchema = z.object({
  title: z.string().min(1, 'Title is required'),
  dueDate: z.string().min(1, 'Due date is required'),
  deadlineType: z.string().min(1),
  description: z.string().optional(),
})

export type DeadlineCreateFormData = z.infer<typeof deadlineCreateSchema>

export const assessmentCreateSchema = z.object({
  title: z.string().min(1, 'Title is required'),
  assessmentType: z.string().min(1),
  weightPct: z
    .string()
    .optional()
    .refine(
      (v) => v === undefined || v === '' || (!Number.isNaN(Number(v)) && Number(v) >= 0 && Number(v) <= 100),
      'Enter a number between 0 and 100',
    ),
  description: z.string().optional(),
})

export type AssessmentCreateFormData = z.infer<typeof assessmentCreateSchema>

// ── Settings (D9) ──────────────────────────────────────────────

export const AGENT_BACKENDS = ['claude_code', 'anthropic_api', 'openai', 'zai', 'ollama'] as const
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
  zai_api_key: z.string(),
  zai_model: z.string(),
  zai_base_url: z
    .string()
    .refine((v) => v === '' || /^https?:\/\/\S+$/.test(v), { message: 'Must be an http(s) URL' }),
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
    invite_code: z.string().optional(),
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

export const captureSchema = z
  .object({
    text: z.string().trim().optional(),
    url: z.string().trim().optional(),
    title: z.string().trim().max(200, 'Title too long').optional(),
  })
  .superRefine((data, ctx) => {
    const hasText = !!data.text
    const hasUrl = !!data.url
    if (hasText && hasUrl) {
      ctx.addIssue({
        code: 'custom',
        message: 'Provide either text or a URL, not both',
        path: ['text'],
      })
    }
    if (!hasText && !hasUrl) {
      ctx.addIssue({
        code: 'custom',
        message: 'Paste some text or enter a URL',
        path: ['text'],
      })
    }
    if (hasUrl && !/^https?:\/\/\S+$/i.test(data.url ?? '')) {
      ctx.addIssue({
        code: 'custom',
        message: 'Enter a valid http(s) URL',
        path: ['url'],
      })
    }
  })

export type CaptureFormData = z.infer<typeof captureSchema>
