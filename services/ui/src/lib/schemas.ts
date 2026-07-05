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
