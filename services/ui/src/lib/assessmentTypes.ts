/**
 * The assessment/deadline type vocabulary, and its display labels.
 *
 * These were previously rendered by capitalising the raw value
 * (`t.charAt(0).toUpperCase() + t.slice(1)`), which produced English from a
 * wire value and — because the loop variable was also called `t` — shadowed
 * the translation function in every one of those blocks.
 */
export const ASSESSMENT_TYPES = [
  'exam',
  'assignment',
  'quiz',
  'project',
  'lab',
  'presentation',
  'other',
] as const

export type AssessmentType = (typeof ASSESSMENT_TYPES)[number]

//: Keys, translated at the render site.
export const ASSESSMENT_TYPE_LABELS: Record<string, string> = {
  exam: 'Exam',
  assignment: 'Assignment',
  quiz: 'Quiz',
  project: 'Project',
  lab: 'Lab',
  presentation: 'Presentation',
  other: 'Other',
}
