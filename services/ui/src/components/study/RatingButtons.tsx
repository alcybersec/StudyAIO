interface RatingButtonsProps {
  onRate: (quality: number) => void
  disabled?: boolean
}

const ratings = [
  { quality: 1, label: 'Again', shortcut: '1', color: 'bg-red-500 hover:bg-red-600', hint: '< 1 min' },
  { quality: 2, label: 'Hard', shortcut: '2', color: 'bg-orange-500 hover:bg-orange-600', hint: '~1 day' },
  { quality: 3, label: 'Good', shortcut: '3', color: 'bg-green-500 hover:bg-green-600', hint: '~3 days' },
  { quality: 5, label: 'Easy', shortcut: '4', color: 'bg-blue-500 hover:bg-blue-600', hint: '~7 days' },
]

export function RatingButtons({ onRate, disabled }: RatingButtonsProps) {
  return (
    <div className="space-y-3">
      <p className="text-center text-sm text-gray-500">How well did you know this?</p>
      <div className="flex items-center justify-center gap-3 flex-wrap">
        {ratings.map((r) => (
          <button
            key={r.quality}
            onClick={() => onRate(r.quality)}
            disabled={disabled}
            className={`flex flex-col items-center px-5 py-3 rounded-lg text-white font-medium transition-colors min-w-[80px] min-h-[56px] disabled:opacity-40 ${r.color}`}
          >
            <span className="text-sm">{r.label}</span>
            <span className="text-[10px] opacity-80">{r.hint}</span>
          </button>
        ))}
      </div>
      <p className="text-center text-xs text-gray-400">
        Keyboard: 1 = Again, 2 = Hard, 3 = Good, 4 = Easy
      </p>
    </div>
  )
}
