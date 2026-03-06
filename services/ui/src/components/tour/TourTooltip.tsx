interface TourTooltipProps {
  title: string
  description: string
  step: number
  totalSteps: number
  position: { top: number; left: number; width: number; height: number }
  onNext: () => void
  onPrev: () => void
  onSkip: () => void
}

export function TourTooltip({
  title,
  description,
  step,
  totalSteps,
  position,
  onNext,
  onPrev,
  onSkip,
}: TourTooltipProps) {
  const isLast = step === totalSteps - 1
  const isFirst = step === 0

  // Position tooltip below the target element
  const tooltipTop = position.top + position.height + 12
  // Center horizontally, clamped to viewport
  const tooltipLeft = Math.max(16, Math.min(position.left + position.width / 2 - 160, window.innerWidth - 336))

  return (
    <div
      className="fixed z-[10001] w-80 bg-surface border border-border rounded-xl shadow-xl p-4"
      style={{ top: `${tooltipTop}px`, left: `${tooltipLeft}px` }}
    >
      {/* Arrow */}
      <div
        className="absolute -top-2 w-4 h-4 bg-surface border-l border-t border-border rotate-45"
        style={{ left: `${Math.max(20, Math.min(position.left + position.width / 2 - tooltipLeft, 280))}px` }}
      />

      <div className="relative">
        <h3 className="text-sm font-semibold text-text mb-1">{title}</h3>
        <p className="text-xs text-text-muted mb-4 leading-relaxed">{description}</p>

        <div className="flex items-center justify-between">
          <span className="text-xs text-text-muted">
            {step + 1} of {totalSteps}
          </span>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onSkip}
              className="px-2 py-1 text-xs text-text-muted hover:text-text transition-colors"
            >
              Skip
            </button>
            {!isFirst && (
              <button
                type="button"
                onClick={onPrev}
                className="px-3 py-1.5 text-xs font-medium rounded-md border border-border text-text hover:bg-surface-alt transition-colors"
              >
                Back
              </button>
            )}
            <button
              type="button"
              onClick={onNext}
              className="px-3 py-1.5 text-xs font-medium rounded-md bg-primary text-white hover:bg-primary/90 transition-colors"
            >
              {isLast ? 'Done' : 'Next'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
