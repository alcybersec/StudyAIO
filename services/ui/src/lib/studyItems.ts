import i18n from '../i18n'
import { AppApiError } from '../api/errors'
import type { QuizQuestion, QuizQuestionCreate, UploadPlacement } from '../types'
import { userErrorMessage } from './userError'

/** Mirrors the backend bounds for manual study items and upload placement. */
export const MAX_ITEM_TEXT = 4000
export const MIN_OPTIONS = 2
export const MAX_OPTIONS = 8
export const MIN_WEEK = 1
export const MAX_WEEK = 52
export const MAX_COURSE_CODE = 20

const LETTERS = 'ABCDEFGH'

export type FieldErrors<K extends string> = Partial<Record<K, string>>

function textError(value: string): string | undefined {
  const v = value.trim()
  if (!v) return i18n.t('This field is required')
  if (v.length > MAX_ITEM_TEXT) return i18n.t('Keep it under {{max}} characters', { max: MAX_ITEM_TEXT })
  return undefined
}

export function validateFlashcard(input: { front: string; back: string }): FieldErrors<'front' | 'back'> {
  const errors: FieldErrors<'front' | 'back'> = {}
  const front = textError(input.front)
  const back = textError(input.back)
  if (front) errors.front = front
  if (back) errors.back = back
  return errors
}

export interface QuizDraft {
  type: 'multiple_choice' | 'short_answer'
  question: string
  options: string[]
  /** Index into `options` for multiple choice. */
  correctIndex: number | null
  /** Model answer for short answer. */
  answer: string
  explanation: string
}

export type QuizField = 'question' | 'options' | 'correct' | 'answer' | 'explanation'

export function validateQuiz(draft: QuizDraft): FieldErrors<QuizField> {
  const errors: FieldErrors<QuizField> = {}
  const q = textError(draft.question)
  if (q) errors.question = q
  if (draft.explanation.trim().length > MAX_ITEM_TEXT) {
    errors.explanation = i18n.t('Keep it under {{max}} characters', { max: MAX_ITEM_TEXT })
  }
  if (draft.type === 'multiple_choice') {
    const filled = draft.options.filter((o) => o.trim())
    if (filled.length < MIN_OPTIONS || filled.length > MAX_OPTIONS || filled.length !== draft.options.length) {
      errors.options = i18n.t('Give {{min}} to {{max}} options, none left blank', {
        min: MIN_OPTIONS,
        max: MAX_OPTIONS,
      })
    } else if (draft.options.some((o) => o.trim().length > MAX_ITEM_TEXT)) {
      errors.options = i18n.t('Keep it under {{max}} characters', { max: MAX_ITEM_TEXT })
    }
    if (draft.correctIndex === null || draft.correctIndex >= draft.options.length) {
      errors.correct = i18n.t('Mark the correct option')
    }
  } else {
    const a = textError(draft.answer)
    if (a) errors.answer = a
  }
  return errors
}

/** Options are stored lettered ("A. text") so the quiz runner can compare on the first character. */
export function letterOptions(options: string[]): string[] {
  return options.map((o, i) => `${LETTERS[i]}. ${o.trim()}`)
}

const LETTER_PREFIX = /^[A-H][.)]\s+/

/** Turn a stored question back into an editable draft. */
export function draftFromQuestion(q: QuizQuestion): QuizDraft {
  if (q.question_type === 'multiple_choice') {
    const raw = q.options_json ?? []
    const idx = raw.findIndex(
      (o, i) => q.correct_answer === LETTERS[i] || o === q.correct_answer || o.charAt(0) === q.correct_answer,
    )
    return {
      type: 'multiple_choice',
      question: q.question,
      options: raw.map((o) => o.replace(LETTER_PREFIX, '')),
      correctIndex: idx >= 0 ? idx : null,
      answer: '',
      explanation: q.explanation ?? '',
    }
  }
  return {
    type: 'short_answer',
    question: q.question,
    options: ['', ''],
    correctIndex: null,
    answer: q.correct_answer,
    explanation: q.explanation ?? '',
  }
}

export function quizPayload(draft: QuizDraft): Omit<QuizQuestionCreate, 'course_code' | 'week'> {
  const base = {
    question_type: draft.type,
    question: draft.question.trim(),
    explanation: draft.explanation.trim() || undefined,
  }
  if (draft.type === 'multiple_choice') {
    return { ...base, options: letterOptions(draft.options), correct_answer: LETTERS[draft.correctIndex ?? 0] }
  }
  return { ...base, correct_answer: draft.answer.trim() }
}

/** The week has no lecture to attach a hand-made item to. */
export function isNoSourceArtifact(err: unknown): boolean {
  return (
    err instanceof AppApiError &&
    err.status === 409 &&
    (err.code === 'no_source_artifact' || err.message === 'no_source_artifact')
  )
}

export function studyItemErrorMessage(err: unknown): string {
  if (isNoSourceArtifact(err)) return i18n.t('Upload a lecture for this week first')
  return userErrorMessage(err, i18n.t("Couldn't save that. Try again."))
}

// ── Upload placement ───────────────────────────────────────────

export interface PlacementDraft {
  /** `auto` lets the classifier decide; `manual` uses course + week below. */
  mode: 'auto' | 'manual'
  course: string
  week: string
}

export const AUTO_PLACEMENT: PlacementDraft = { mode: 'auto', course: '', week: '' }

export function validatePlacement(draft: PlacementDraft): FieldErrors<'course' | 'week'> {
  if (draft.mode === 'auto') return {}
  const errors: FieldErrors<'course' | 'week'> = {}
  const code = draft.course.trim()
  if (!code) errors.course = i18n.t('Choose a course, or let StudyAIO decide')
  else if (code.length > MAX_COURSE_CODE) {
    errors.course = i18n.t('Course codes are at most {{max}} characters', { max: MAX_COURSE_CODE })
  }
  const w = draft.week.trim()
  if (!/^\d+$/.test(w) || Number(w) < MIN_WEEK || Number(w) > MAX_WEEK) {
    errors.week = i18n.t('Enter a week from {{min}} to {{max}}', { min: MIN_WEEK, max: MAX_WEEK })
  }
  return errors
}

/** The placement to send, or undefined for "let StudyAIO decide". Callers must validate first. */
export function placementFromDraft(draft: PlacementDraft): UploadPlacement | undefined {
  if (draft.mode === 'auto') return undefined
  return { course_code: draft.course.trim(), week: Number(draft.week.trim()) }
}
