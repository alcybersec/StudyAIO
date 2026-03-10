import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { useTour } from '../../hooks/useTour'
import { useAuth } from '../../hooks/useAuth'
import { TourTooltip } from './TourTooltip'

export function OnboardingTour() {
  const { isDemo } = useAuth()
  const { active, step, currentStep, totalSteps, completed, start, next, prev, skip } = useTour()
  const [targetRect, setTargetRect] = useState<DOMRect | null>(null)

  // Auto-start tour for demo users who haven't completed it
  useEffect(() => {
    if (isDemo && !completed && !active) {
      // Small delay to let the page render first
      const timer = setTimeout(() => start(0), 500)
      return () => clearTimeout(timer)
    }
  }, [isDemo, completed, active, start])

  // Find and track the target element (DOM measurement requires setState in effect)
  useEffect(() => {
    if (!active || !currentStep) {
      setTargetRect(null) // eslint-disable-line react-hooks/set-state-in-effect
      return
    }

    const findTarget = () => {
      const el = document.querySelector(`[data-tour="${currentStep.target}"]`)
      if (el) {
        const rect = el.getBoundingClientRect()
        setTargetRect(rect)
        // Scroll into view if needed
        el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      } else {
        setTargetRect(null)
      }
    }

    findTarget()
    // Re-check position on scroll/resize
    const handleUpdate = () => findTarget()
    window.addEventListener('scroll', handleUpdate, true)
    window.addEventListener('resize', handleUpdate)
    return () => {
      window.removeEventListener('scroll', handleUpdate, true)
      window.removeEventListener('resize', handleUpdate)
    }
  }, [active, currentStep, step])

  if (!active || !currentStep || !targetRect) return null

  const padding = 6

  return createPortal(
    <>
      {/* Spotlight overlay using box-shadow */}
      <div
        className="fixed z-[10000] rounded-lg pointer-events-none"
        style={{
          top: `${targetRect.top - padding}px`,
          left: `${targetRect.left - padding}px`,
          width: `${targetRect.width + padding * 2}px`,
          height: `${targetRect.height + padding * 2}px`,
          boxShadow: '0 0 0 9999px rgba(0, 0, 0, 0.5)',
        }}
      />
      {/* Clickable overlay to prevent interaction behind */}
      <div className="fixed inset-0 z-[9999]" onClick={skip} />
      {/* Tooltip */}
      <TourTooltip
        title={currentStep.title}
        description={currentStep.description}
        step={step}
        totalSteps={totalSteps}
        position={{
          top: targetRect.top,
          left: targetRect.left,
          width: targetRect.width,
          height: targetRect.height,
        }}
        onNext={next}
        onPrev={prev}
        onSkip={skip}
      />
    </>,
    document.body,
  )
}
