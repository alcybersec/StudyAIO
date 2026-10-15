import { describe, expect, it } from 'vitest'
import { AppApiError } from '../api/errors'
import {
  AUTO_PLACEMENT,
  draftFromQuestion,
  isNoSourceArtifact,
  placementFromDraft,
  quizPayload,
  studyItemErrorMessage,
  validateFlashcard,
  validatePlacement,
  validateQuiz,
  type QuizDraft,
} from './studyItems'
import type { QuizQuestion } from '../types'

const mc = (over: Partial<QuizDraft> = {}): QuizDraft => ({
  type: 'multiple_choice',
  question: 'Q?',
  options: ['one', 'two'],
  correctIndex: 1,
  answer: '',
  explanation: '',
  ...over,
})

describe('validateFlashcard', () => {
  it('accepts text and rejects blank or over-long fields', () => {
    expect(validateFlashcard({ front: 'a', back: 'b' })).toEqual({})
    expect(validateFlashcard({ front: '  ', back: 'b' }).front).toBeDefined()
    expect(validateFlashcard({ front: 'a', back: 'x'.repeat(4001) }).back).toBeDefined()
    expect(validateFlashcard({ front: 'a', back: 'x'.repeat(4000) })).toEqual({})
  })
})

describe('validateQuiz', () => {
  it('accepts a well-formed multiple-choice draft', () => {
    expect(validateQuiz(mc())).toEqual({})
  })
  it('needs 2 to 8 non-blank options and a marked answer', () => {
    expect(validateQuiz(mc({ options: ['only'], correctIndex: 0 })).options).toBeDefined()
    expect(validateQuiz(mc({ options: ['a', ''] })).options).toBeDefined()
    expect(validateQuiz(mc({ options: Array(9).fill('x'), correctIndex: 0 })).options).toBeDefined()
    expect(validateQuiz(mc({ correctIndex: null })).correct).toBeDefined()
  })
  it('short answer needs a model answer and ignores options', () => {
    const d = mc({ type: 'short_answer', options: [], correctIndex: null, answer: '' })
    expect(validateQuiz(d).answer).toBeDefined()
    expect(validateQuiz({ ...d, answer: 'ok' })).toEqual({})
  })
})

describe('quiz payload mapping', () => {
  it('letters the options and sends the correct letter', () => {
    expect(quizPayload(mc())).toMatchObject({
      question_type: 'multiple_choice',
      options: ['A. one', 'B. two'],
      correct_answer: 'B',
    })
  })
  it('round-trips a stored question into a draft', () => {
    const q = {
      question_type: 'multiple_choice',
      question: 'Q',
      options_json: ['A) Queue', 'B) Stack'],
      correct_answer: 'B',
      explanation: 'e',
    } as QuizQuestion
    const d = draftFromQuestion(q)
    expect(d.options).toEqual(['Queue', 'Stack'])
    expect(d.correctIndex).toBe(1)
  })
})

describe('error messages', () => {
  it('maps 409 no_source_artifact to the actionable message', () => {
    const e = new AppApiError('no_source_artifact', 409)
    expect(isNoSourceArtifact(e)).toBe(true)
    expect(studyItemErrorMessage(e)).toBe('Upload a lecture for this week first')
  })
  it('does not treat other 409s that way', () => {
    expect(isNoSourceArtifact(new AppApiError('dup', 409))).toBe(false)
  })
})

describe('upload placement', () => {
  it('auto needs nothing and sends no placement', () => {
    expect(validatePlacement(AUTO_PLACEMENT)).toEqual({})
    expect(placementFromDraft(AUTO_PLACEMENT)).toBeUndefined()
  })
  it('manual needs both a course and a week', () => {
    expect(validatePlacement({ mode: 'manual', course: 'CSIT302', week: '' }).week).toBeDefined()
    expect(validatePlacement({ mode: 'manual', course: '', week: '4' }).course).toBeDefined()
    expect(validatePlacement({ mode: 'manual', course: '  ', week: '4' }).course).toBeDefined()
  })
  it('bounds the week to 1-52 and the code to 20 chars', () => {
    for (const w of ['0', '53', '1.5', 'x', '-1']) {
      expect(validatePlacement({ mode: 'manual', course: 'C', week: w }).week).toBeDefined()
    }
    for (const w of ['1', '52']) {
      expect(validatePlacement({ mode: 'manual', course: 'C', week: w })).toEqual({})
    }
    expect(validatePlacement({ mode: 'manual', course: 'x'.repeat(21), week: '3' }).course).toBeDefined()
  })
  it('produces trimmed course and numeric week', () => {
    expect(placementFromDraft({ mode: 'manual', course: ' CSIT302 ', week: ' 5 ' })).toEqual({
      course_code: 'CSIT302',
      week: 5,
    })
  })
})
