import { useState, useEffect, useCallback, useMemo } from 'react'
import { useFlashcards } from '../../hooks/useApi'
import { LoadingSpinner, EmptyState, Badge } from '../ui'

interface FlashcardsTabProps {
  courseCode: string
  week: number
}

export function FlashcardsTab({ courseCode, week }: FlashcardsTabProps) {
  const { data: flashcards, isLoading, error } = useFlashcards(courseCode, week)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [shuffled, setShuffled] = useState(false)

  const cards = useMemo(() => {
    if (!flashcards) return []
    if (!shuffled) return flashcards
    return [...flashcards].sort(() => Math.random() - 0.5)
  }, [flashcards, shuffled])

  const card = cards[currentIndex]

  const goNext = useCallback(() => {
    if (currentIndex < cards.length - 1) {
      setCurrentIndex((i) => i + 1)
      setFlipped(false)
    }
  }, [currentIndex, cards.length])

  const goPrev = useCallback(() => {
    if (currentIndex > 0) {
      setCurrentIndex((i) => i - 1)
      setFlipped(false)
    }
  }, [currentIndex])

  const toggleFlip = useCallback(() => setFlipped((f) => !f), [])

  const toggleShuffle = useCallback(() => {
    setShuffled((s) => !s)
    setCurrentIndex(0)
    setFlipped(false)
  }, [])

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === ' ' || e.key === 'Enter') {
        e.preventDefault()
        toggleFlip()
      } else if (e.key === 'ArrowRight') {
        goNext()
      } else if (e.key === 'ArrowLeft') {
        goPrev()
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [toggleFlip, goNext, goPrev])

  if (isLoading) return <LoadingSpinner label="Loading flashcards..." />
  if (error) return <EmptyState icon="!" title="Failed to load flashcards" />
  if (!cards.length) {
    return (
      <EmptyState
        icon="?"
        title="No flashcards yet"
        description="Flashcards will be generated when the pipeline processes lecture files."
      />
    )
  }

  return (
    <div className="flex flex-col items-center gap-6 py-4">
      {/* Counter + Shuffle */}
      <div className="flex items-center gap-4 text-sm text-gray-500">
        <span className="font-medium">
          {currentIndex + 1} / {cards.length}
        </span>
        <button
          onClick={toggleShuffle}
          className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
            shuffled
              ? 'bg-primary/10 text-primary'
              : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
          }`}
        >
          Shuffle {shuffled ? 'On' : 'Off'}
        </button>
      </div>

      {/* Card */}
      <button
        onClick={toggleFlip}
        className="w-full max-w-xl min-h-[220px] rounded-xl border border-gray-200 bg-white shadow-sm hover:shadow-md transition-shadow cursor-pointer p-8 text-center focus:outline-none focus:ring-2 focus:ring-primary/50"
        aria-label={flipped ? 'Showing answer, click to see question' : 'Showing question, click to see answer'}
      >
        <div className="text-xs uppercase tracking-wider text-gray-400 mb-4">
          {flipped ? 'Answer' : 'Question'}
        </div>
        <div className="text-lg leading-relaxed text-gray-800 whitespace-pre-wrap">
          {flipped ? card.back : card.front}
        </div>
      </button>

      {/* Tags + Page ref */}
      <div className="flex items-center gap-2 flex-wrap justify-center">
        {card.tags.map((tag: string) => (
          <Badge key={tag} variant="default">
            {tag}
          </Badge>
        ))}
        <span className="text-xs text-gray-400">p.{card.source_page_ref}</span>
      </div>

      {/* Navigation */}
      <div className="flex items-center gap-3">
        <button
          onClick={goPrev}
          disabled={currentIndex === 0}
          className="px-4 py-2 rounded-lg text-sm font-medium bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Previous
        </button>
        <button
          onClick={toggleFlip}
          className="px-4 py-2 rounded-lg text-sm font-medium bg-primary text-white hover:bg-primary/90 transition-colors"
        >
          Flip
        </button>
        <button
          onClick={goNext}
          disabled={currentIndex === cards.length - 1}
          className="px-4 py-2 rounded-lg text-sm font-medium bg-gray-100 text-gray-700 hover:bg-gray-200 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Next
        </button>
      </div>

      <p className="text-xs text-gray-400">
        Space to flip, arrow keys to navigate
      </p>
    </div>
  )
}
