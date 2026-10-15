/** Router state that hands "Study tonight" items to the timed study runner. */
export interface PlanRunState {
  cardIds: string[]
  quizIds: string[]
  minutes: number
  courseCodes: string[]
}
