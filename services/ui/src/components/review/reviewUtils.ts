import type { ReviewItem } from '../../types'

export type ConfidenceTone = 'danger' | 'warning' | 'success'

/** Badge tone for a confidence percentage: red < 40, amber < 60, sage above. */
export function confidenceTone(pct: number): ConfidenceTone {
  if (pct < 40) return 'danger'
  if (pct < 60) return 'warning'
  return 'success'
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : null
}

function toPct(confidence: number): number {
  return Math.round(confidence <= 1 ? confidence * 100 : confidence)
}

/** Classifier confidence as a 0-100 percentage, or null when unavailable. */
export function itemConfidencePct(item: ReviewItem): number | null {
  const payload = item.payload_json ?? {}
  const suggestions = payload.suggestions
  if (Array.isArray(suggestions) && suggestions.length > 0) {
    const first = asRecord(suggestions[0])
    if (first && typeof first.confidence === 'number') return toPct(first.confidence)
  }
  if (typeof payload.confidence === 'number') return toPct(payload.confidence)
  return null
}

/** Original filename from the review payload. */
export function itemFilename(item: ReviewItem): string | null {
  const payload = item.payload_json ?? {}
  if (typeof payload.original_filename === 'string') return payload.original_filename
  if (typeof payload.filename === 'string') return payload.filename
  return null
}

/** Human-readable reason the item needs review. */
export function itemReason(item: ReviewItem): string | null {
  const payload = item.payload_json ?? {}
  if (typeof payload.reason === 'string') return payload.reason
  if (typeof payload.message === 'string') return payload.message
  return null
}

export interface ReviewGuess {
  courseCode: string | null
  week: number | null
  title: string | null
}

/** The pipeline's suggested classification for the item. */
export function itemGuess(item: ReviewItem): ReviewGuess {
  const suggested = item.suggested_values ?? {}
  return {
    courseCode: typeof suggested.course_code === 'string' ? suggested.course_code : null,
    week: typeof suggested.week === 'number' ? suggested.week : null,
    title: typeof suggested.title === 'string' ? suggested.title : null,
  }
}

/**
 * Resolution payload for one-key approval of the pipeline's guess.
 * Returns null when there is no usable course suggestion (approval would
 * silently mis-file the artifact) — the row falls back to Edit.
 */
export function approveResolution(item: ReviewItem): Record<string, unknown> | null {
  const guess = itemGuess(item)
  if (!guess.courseCode || guess.courseCode === 'UNKNOWN') return null
  const resolution: Record<string, unknown> = { course_code: guess.courseCode }
  if (guess.week !== null) resolution.week = guess.week
  if (guess.title !== null) resolution.title = guess.title
  return resolution
}
