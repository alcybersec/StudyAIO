import type { Flashcard } from '../../types'
import { Badge } from '../ui'

interface StudyCardProps {
  card: Flashcard
  onFlip: () => void
  flipped: boolean
}

export function StudyCard({ card, onFlip, flipped }: StudyCardProps) {
  return (
    <div className="w-full max-w-xl mx-auto perspective-1000">
      <button
        onClick={onFlip}
        className="relative w-full min-h-[260px] cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary/50 rounded-xl"
        aria-label={flipped ? 'Showing answer, click to see question' : 'Showing question, click to see answer'}
      >
        <div
          className={`relative w-full min-h-[260px] transition-transform duration-500 preserve-3d ${
            flipped ? 'rotate-y-180' : ''
          }`}
          style={{ transformStyle: 'preserve-3d' }}
        >
          {/* Front */}
          <div
            className="absolute inset-0 rounded-xl border border-gray-200 bg-white shadow-sm p-8 flex flex-col items-center justify-center text-center"
            style={{ backfaceVisibility: 'hidden' }}
          >
            <div className="text-xs uppercase tracking-wider text-gray-400 mb-4">Question</div>
            <div className="text-lg leading-relaxed text-gray-800 whitespace-pre-wrap">
              {card.front}
            </div>
          </div>

          {/* Back */}
          <div
            className="absolute inset-0 rounded-xl border border-gray-200 bg-gradient-to-br from-white to-gray-50 shadow-sm p-8 flex flex-col items-center justify-center text-center"
            style={{ backfaceVisibility: 'hidden', transform: 'rotateY(180deg)' }}
          >
            <div className="text-xs uppercase tracking-wider text-gray-400 mb-4">Answer</div>
            <div className="text-lg leading-relaxed text-gray-800 whitespace-pre-wrap">
              {card.back}
            </div>
            <div className="flex items-center gap-2 flex-wrap justify-center mt-4">
              {card.tags.map((tag: string) => (
                <Badge key={tag} variant="default">
                  {tag}
                </Badge>
              ))}
            </div>
          </div>
        </div>
      </button>

      {!flipped && (
        <p className="text-center text-xs text-gray-400 mt-3">
          Press Space or click to reveal answer
        </p>
      )}
    </div>
  )
}
