import { useCallback, useState, useSyncExternalStore } from 'react'

const TOUR_COMPLETED_KEY = 'studyaio_tour_completed'
const TOUR_STEP_KEY = 'studyaio_tour_step'

export interface TourStep {
  target: string // data-tour attribute value
  title: string
  description: string
}

export const TOUR_STEPS: TourStep[] = [
  {
    target: 'dashboard',
    title: 'Dashboard',
    description: 'Your command center — track study progress, upcoming exams, and recent activity at a glance.',
  },
  {
    target: 'upload',
    title: 'Upload Lectures',
    description: 'Drop PDFs, DOCX, or PPTX files here. The AI pipeline extracts, summarizes, and creates study materials automatically.',
  },
  {
    target: 'study',
    title: 'Study Hub',
    description: 'Flashcards with spaced repetition, timed study sessions, quizzes, and exam prep — all in one place.',
  },
  {
    target: 'ask',
    title: 'Ask',
    description: 'Ask questions about your lectures. The AI uses your materials to give accurate, cited answers — scope to a course or week for sharper retrieval.',
  },
  {
    target: 'knowledge',
    title: 'Knowledge Graph',
    description: 'Visualize how concepts from your lectures connect in an interactive graph.',
  },
  {
    target: 'analytics',
    title: 'Analytics',
    description: 'Track your study patterns, retention rates, and identify weak areas to focus on.',
  },
  {
    target: 'settings',
    title: 'Settings',
    description: 'Configure AI providers, theme, pipeline tuning, and notification preferences.',
  },
]

// External store for cross-component reactivity
let listeners: Array<() => void> = []
function subscribe(listener: () => void) {
  listeners = [...listeners, listener]
  return () => {
    listeners = listeners.filter((l) => l !== listener)
  }
}
function emitChange() {
  for (const listener of listeners) {
    listener()
  }
}

function getCompleted(): boolean {
  return localStorage.getItem(TOUR_COMPLETED_KEY) === 'true'
}

function getSavedStep(): number {
  const val = localStorage.getItem(TOUR_STEP_KEY)
  return val ? parseInt(val, 10) : 0
}

export function useTour() {
  const completed = useSyncExternalStore(subscribe, getCompleted, () => true)
  const [active, setActive] = useState(false)
  const [step, setStep] = useState(getSavedStep)

  const start = useCallback((fromStep = 0) => {
    setStep(fromStep)
    localStorage.setItem(TOUR_STEP_KEY, String(fromStep))
    setActive(true)
  }, [])

  const next = useCallback(() => {
    setStep((prev) => {
      const nextStep = prev + 1
      if (nextStep >= TOUR_STEPS.length) {
        // Tour complete
        localStorage.setItem(TOUR_COMPLETED_KEY, 'true')
        localStorage.removeItem(TOUR_STEP_KEY)
        setActive(false)
        emitChange()
        return prev
      }
      localStorage.setItem(TOUR_STEP_KEY, String(nextStep))
      return nextStep
    })
  }, [])

  const prev = useCallback(() => {
    setStep((s) => {
      const prevStep = Math.max(0, s - 1)
      localStorage.setItem(TOUR_STEP_KEY, String(prevStep))
      return prevStep
    })
  }, [])

  const skip = useCallback(() => {
    localStorage.setItem(TOUR_COMPLETED_KEY, 'true')
    localStorage.removeItem(TOUR_STEP_KEY)
    setActive(false)
    emitChange()
  }, [])

  const replay = useCallback(() => {
    localStorage.removeItem(TOUR_COMPLETED_KEY)
    localStorage.removeItem(TOUR_STEP_KEY)
    emitChange()
    start(0)
  }, [start])

  return {
    active,
    step,
    currentStep: TOUR_STEPS[step] ?? null,
    totalSteps: TOUR_STEPS.length,
    completed,
    start,
    next,
    prev,
    skip,
    replay,
  }
}
