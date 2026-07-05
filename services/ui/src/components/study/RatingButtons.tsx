import { Kbd } from '../ui'

interface RatingButtonsProps {
  onRate: (quality: number) => void
  disabled?: boolean
}

const ratings = [
  { quality: 1, label: 'Again', shortcut: '1', tone: 'bg-red-soft text-red-fg', hint: '< 1 min' },
  { quality: 2, label: 'Hard', shortcut: '2', tone: 'bg-amber-soft text-amber-fg', hint: '~1 day' },
  { quality: 3, label: 'Good', shortcut: '3', tone: 'bg-sage-soft text-sage-fg', hint: '~3 days' },
  { quality: 5, label: 'Easy', shortcut: '4', tone: 'bg-peri-soft text-peri-fg', hint: '~7 days' },
]

export function RatingButtons({ onRate, disabled }: RatingButtonsProps) {
  return (
    <div className="w-full max-w-xl mx-auto space-y-3">
      <div className="grid grid-cols-4 gap-1.5" aria-label="Rate recall">
        {ratings.map((r) => (
          <button
            key={r.quality}
            onClick={() => onRate(r.quality)}
            disabled={disabled}
            title={`${r.label} — next review ${r.hint}`}
            className={`text-xs font-medium rounded-lg py-2.5 min-h-[56px] cursor-pointer transition-opacity hover:opacity-80 disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-peri ${r.tone}`}
          >
            {r.label}
            <span className="block font-mono text-[9px] opacity-70 mt-0.5">{r.shortcut}</span>
          </button>
        ))}
      </div>
      <p className="text-center text-[11px] font-mono text-text-faint">
        <Kbd>1</Kbd> again · <Kbd>2</Kbd> hard · <Kbd>3</Kbd> good · <Kbd>4</Kbd> easy
      </p>
    </div>
  )
}
