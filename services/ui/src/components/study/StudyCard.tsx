import type { Flashcard } from '../../types'
import { Badge, Kbd } from '../ui'

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
        className="relative w-full min-h-[260px] cursor-pointer rounded-xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-peri"
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
            className="absolute inset-0 rounded-xl border border-border bg-surface-1 shadow-sm p-8 flex flex-col items-center justify-center text-center"
            style={{ backfaceVisibility: 'hidden' }}
          >
            <div className="text-[10px] font-mono uppercase tracking-[0.1em] text-text-faint mb-4">Question</div>
            <div className="text-lg leading-relaxed text-text whitespace-pre-wrap">
              {card.front}
            </div>
          </div>

          {/* Back */}
          <div
            className="absolute inset-0 rounded-xl border border-border bg-gradient-to-br from-surface-1 to-surface-2 shadow-sm p-8 flex flex-col items-center justify-center text-center"
            style={{ backfaceVisibility: 'hidden', transform: 'rotateY(180deg)' }}
          >
            <div className="text-[10px] font-mono uppercase tracking-[0.1em] text-text-faint mb-4">Answer</div>
            <div className="text-lg leading-relaxed text-text whitespace-pre-wrap">
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
        <p className="text-center text-[11px] font-mono text-text-faint mt-3">
          <Kbd>space</Kbd> reveal answer
        </p>
      )}
    </div>
  )
}
