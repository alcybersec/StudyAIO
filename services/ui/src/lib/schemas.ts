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
