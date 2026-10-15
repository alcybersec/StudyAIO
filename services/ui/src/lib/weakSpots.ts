import i18n from '../i18n'
import { AppApiError } from '../api/errors'
import type {
  TargetedGeneration,
  TonightItem,
  TonightPlan,
  WeakSpotStatus,
} from '../types'

/** The four states the heatmap draws. Unknown is its own state, never a shade of weak. */
export type MasteryState = 'unknown' | 'weak' | 'ok' | 'solid'

export const MASTERY_STATES: readonly MasteryState[] = ['unknown', 'weak', 'ok', 'solid']

/** ADR 0007 Decision 2 names the middle band `shaky`; the UI calls it `ok`. */
export function masteryState(status: WeakSpotStatus | string | null | undefined): MasteryState {
  switch (status) {
    case 'weak':
      return 'weak'
    case 'shaky':
    case 'ok':
      return 'ok'
    case 'solid':
      return 'solid'
    default:
      // Anything not understood is treated as "no verdict", never as a warning.
      return 'unknown'
  }
}

/** Cell colour classes. Unknown is a neutral dashed surface; red is reserved for `weak`. */
export const MASTERY_CELL_CLASS: Record<MasteryState, string> = {
  unknown: 'bg-surface-2 text-text-muted border-border border-dashed',
  weak: 'bg-red-soft text-red-fg border-red/40',
  ok: 'bg-amber-soft text-amber-fg border-amber/40',
  solid: 'bg-sage-soft text-sage-fg border-sage/40',
}

export function masteryLabel(state: MasteryState): string {
  switch (state) {
    case 'weak':
      return i18n.t('Weak')
    case 'ok':
      return i18n.t('OK')
    case 'solid':
      return i18n.t('Solid')
    default:
      return i18n.t('Not enough data')
  }
}

/** Next 00:00 UTC after `now`: the targeted daily cap resets on the UTC day (ADR 0007 Decision 5). */
export function nextUtcMidnight(now: Date = new Date()): Date {
  return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1))
}

export function isDailyCapError(err: unknown): boolean {
  return err instanceof AppApiError && err.status === 429 && err.code === 'targeted_daily_cap'
}

/** Message for the 429 `targeted_daily_cap`, with the reset time in the viewer's local clock. */
export function dailyCapMessage(now: Date = new Date()): string {
  const time = nextUtcMidnight(now).toLocaleTimeString(i18n.language, {
    hour: '2-digit',
    minute: '2-digit',
  })
  return i18n.t(
    "You've used today's practice generations. You can request more after {{time}} (the limit resets at 00:00 UTC).",
    { time },
  )
}

export function isGenerationActive(g: Pick<TargetedGeneration, 'status'> | undefined): boolean {
  return g?.status === 'queued' || g?.status === 'running'
}

export interface PlanGroup {
  key: string
  course_code: string
  course_id: string
  week: number
  cards: number
  quizzes: number
  minutes: number
  done: number
  total: number
  targeted: boolean
  reasons: TonightItem['reason'][]
}

/** Group the plan's items by (course, week), in first-seen order. */
export function groupPlanItems(items: TonightItem[]): PlanGroup[] {
  const groups = new Map<string, PlanGroup>()
  for (const item of items) {
    const key = `${item.course_id}:${item.week}`
    let g = groups.get(key)
    if (!g) {
      g = {
        key,
        course_code: item.course_code,
        course_id: item.course_id,
        week: item.week,
        cards: 0,
        quizzes: 0,
        minutes: 0,
        done: 0,
        total: 0,
        targeted: false,
        reasons: [],
      }
      groups.set(key, g)
    }
    if (item.item_type === 'card') g.cards += 1
    else g.quizzes += 1
    g.minutes += item.minutes
    g.total += 1
    if (item.done) g.done += 1
    if (item.reason === 'targeted') g.targeted = true
    if (!g.reasons.includes(item.reason)) g.reasons.push(item.reason)
  }
  return [...groups.values()]
}

export function planIsEmpty(plan: TonightPlan): boolean {
  return plan.items.length === 0 && !plan.diagnostic
}

/** Ids of the not-yet-done items, split by type, for the study runner. */
export function runnableIds(plan: TonightPlan): { cardIds: string[]; quizIds: string[] } {
  const open = plan.items.filter((i) => !i.done)
  return {
    cardIds: open.filter((i) => i.item_type === 'card').map((i) => i.item_id),
    quizIds: open.filter((i) => i.item_type === 'quiz').map((i) => i.item_id),
  }
}

export function reasonLabel(reason: TonightItem['reason']): string {
  switch (reason) {
    case 'diagnostic':
      return i18n.t('Check-in')
    case 'missed':
      return i18n.t('Missed before')
    case 'review':
      return i18n.t('Due review')
    case 'targeted':
      return i18n.t('Practice')
    default:
      return i18n.t('New')
  }
}

/** The "why" of a focus week: how weak it is, and how close the exam is. */
export function focusWhy(status: WeakSpotStatus, daysToExam: number | null): string {
  const state = masteryLabel(masteryState(status))
  if (daysToExam == null) return state
  if (daysToExam === 0) return i18n.t('{{state}} · exam today', { state })
  return i18n.t('{{state}} · exam in {{days}}d', { state, days: daysToExam })
}
