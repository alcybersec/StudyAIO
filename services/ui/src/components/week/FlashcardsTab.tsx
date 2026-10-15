import { useState, useEffect, useCallback, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { Pencil, Plus, Trash2 } from 'lucide-react'
import { useDeleteFlashcard, useFlashcards, useStudyStats } from '../../hooks/useApi'
import { studyItemErrorMessage } from '../../lib/studyItems'
import { DeleteItemModal } from './DeleteItemModal'
import { FlashcardEditor } from './FlashcardEditor'
import { OriginBadge } from './OriginBadge'
import { useOnlineStatus } from '../../hooks/useOnlineStatus'
import { AiFeedbackControl } from '../ui/AiFeedbackControl'
import { Badge, Button, EmptyState, ErrorState, Kbd, Skeleton } from '../ui'

interface FlashcardsTabProps {
  courseCode: string
  week: number
}

function FlashcardsSkeleton() {
  return (
    <div className="flex flex-col items-center gap-6 py-4" aria-busy="true">
      <Skeleton width={320} height={44} className="max-w-xl w-full" />
      <Skeleton width={160} height={20} />
      <Skeleton className="w-full max-w-xl" height={220} />
      <Skeleton width={240} height={36} />
    </div>
  )
}

export function FlashcardsTab({ courseCode, week }: FlashcardsTabProps) {
  const { t } = useTranslation()

  const { data: flashcards, isLoading, error, refetch } = useFlashcards(courseCode, week)
  const { data: studyStats } = useStudyStats(courseCode, week)
  const online = useOnlineStatus()
  const [currentIndex, setCurrentIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [shuffledCards, setShuffledCards] = useState<typeof flashcards>()
  const [editor, setEditor] = useState<'add' | 'edit' | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [deleteError, setDeleteError] = useState<string>()
  const deleteCard = useDeleteFlashcard()

  // Drop shuffled copies of cards that were since edited or deleted: the list
  // from the server (new ids after an edit) is the source of truth.
  const live = new Set((flashcards ?? []).map((c) => c.id))
  const shuffled = shuffledCards?.every((c) => live.has(c.id)) && shuffledCards.length === flashcards?.length
    ? shuffledCards
    : undefined
  const cards = shuffled ?? flashcards ?? []
  const card = cards[Math.min(currentIndex, Math.max(cards.length - 1, 0))]
  const flashcardIds = useMemo(() => (flashcards ?? []).map((c) => c.id), [flashcards])

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
    if (shuffled) {
      setShuffledCards(undefined)
    } else if (flashcards) {
      setShuffledCards([...flashcards].sort(() => Math.random() - 0.5))
    }
    setCurrentIndex(0)
    setFlipped(false)
  }, [flashcards, shuffled])

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null
      // Typing in the editor (or pressing a toolbar button) must not flip the card.
      if (target?.closest('input, textarea, select, button, [role="dialog"], [role="radio"]')) return
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

  if (error) {
    return (
      <ErrorState
        title={online ? "Flashcards couldn't load" : "You're offline"}
        detail={error instanceof Error ? error.message : undefined}
        onRetry={() => refetch()}
      />
    )
  }
  if (!flashcards && !online) {
    return (
      <ErrorState
        title={t("You're offline")}
        detail={t("Flashcards for this week haven't been cached. They'll load once you're back online.")}
        onRetry={() => refetch()}
      />
    )
  }
  if (isLoading || !flashcards) return <FlashcardsSkeleton />
  if (!cards.length) {
    return (
      <div className="space-y-4">
        <EmptyState
          title={t('No flashcards yet')}
          description={t('Flashcards will be generated when the pipeline processes lecture files.')}
        />
        <div className="flex justify-center">
          <Button variant="secondary" className="min-h-11" onClick={() => setEditor('add')}>
            <Plus size={14} aria-hidden /> {t('Add card')}
          </Button>
        </div>
        <FlashcardEditor open={editor === 'add'} onOpenChange={(o) => !o && setEditor(null)} courseCode={courseCode} week={week} />
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center gap-6 py-4">
      {/* Study CTA + Stats */}
      {studyStats && (
        <div className="w-full max-w-xl flex items-center justify-between bg-surface-2 rounded-lg px-4 py-3">
          <div className="flex items-center gap-4 text-sm">
            <span className="text-text-muted">
              <span className="font-semibold text-text">{studyStats.mastered}</span> {t('mastered')}
              {' · '}
              <span className="font-semibold text-text">{studyStats.learning}</span> {t('learning')}
              {' · '}
              <span className="font-semibold text-text">{studyStats.new}</span> {t('new')}
            </span>
          </div>
          <Link
            to={`/study?tab=flashcards&course=${courseCode}&week=${week}`}
            className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-semibold text-on-accent bg-sage hover:bg-sage-hover transition-colors min-h-[36px] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-peri"
          >
            {studyStats.due_today > 0 && (
              <span className="bg-surface-0/20 rounded-full px-1.5 py-0.5 text-[10px]">
                {studyStats.due_today}
              </span>
            )}
            {t('Study Now')}
          </Link>
        </div>
      )}

      {/* Counter + Shuffle */}
      <div className="flex items-center gap-4 text-sm text-text-muted">
        <span className="font-mono font-medium">
          {currentIndex + 1} / {cards.length}
        </span>
        <button
          onClick={toggleShuffle}
          className={`px-4 py-2.5 min-h-[44px] rounded-full text-xs font-medium transition-colors cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-peri ${
            shuffled
              ? 'bg-peri-soft text-peri-fg'
              : 'bg-surface-2 text-text-muted hover:text-text'
          }`}
        >
          {t('Shuffle')} {shuffled ? t('On') : t('Off')}
        </button>
      </div>

      {/* Card */}
      <button
        onClick={toggleFlip}
        className="w-full max-w-xl min-h-[220px] rounded-xl border border-border bg-surface-1 shadow-sm hover:shadow-md transition-shadow cursor-pointer p-8 text-center focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-peri"
        aria-label={flipped ? 'Showing answer, click to see question' : 'Showing question, click to see answer'}
      >
        <div className="text-[10px] font-mono uppercase tracking-[0.1em] text-text-faint mb-4">
          {flipped ? t('Answer') : t('Question')}
        </div>
        <div className="text-lg leading-relaxed text-text whitespace-pre-wrap">
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
        <OriginBadge origin={card.origin} />
        {card.source_page_ref > 0 && (
          <span className="text-xs font-mono text-text-faint">p.{card.source_page_ref}</span>
        )}
      </div>

      {/* Manage */}
      <div className="flex flex-wrap items-center justify-center gap-2">
        <Button variant="ghost" size="sm" className="min-h-11" onClick={() => setEditor('edit')}>
          <Pencil size={13} aria-hidden /> {t('Edit')}
        </Button>
        <Button variant="ghost" size="sm" className="min-h-11" onClick={() => { setDeleteError(undefined); setDeleting(true) }}>
          <Trash2 size={13} aria-hidden /> {t('Delete')}
        </Button>
        <Button variant="ghost" size="sm" className="min-h-11" onClick={() => setEditor('add')}>
          <Plus size={13} aria-hidden /> {t('Add card')}
        </Button>
      </div>

      <FlashcardEditor
        open={editor !== null}
        onOpenChange={(o) => !o && setEditor(null)}
        courseCode={courseCode}
        week={week}
        card={editor === 'edit' ? card : undefined}
      />
      <DeleteItemModal
        open={deleting}
        onOpenChange={setDeleting}
        title={t('Delete this flashcard?')}
        preview={card.front}
        pending={deleteCard.isPending}
        error={deleteError}
        onConfirm={() =>
          deleteCard.mutate(card.id, {
            onSuccess: () => setDeleting(false),
            onError: (err) => setDeleteError(studyItemErrorMessage(err)),
          })
        }
      />

      <AiFeedbackControl
        key={card.id}
        targetType="flashcard"
        targetId={card.id}
        batchIds={flashcardIds}
      />

      {/* Navigation */}
      <div className="flex items-center gap-3">
        <button
          onClick={goPrev}
          disabled={currentIndex === 0}
          className="px-4 py-2 rounded-lg text-sm font-medium bg-surface-2 text-text border border-border hover:border-border-strong disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-peri"
        >
          {t('Previous')}
        </button>
        <button
          onClick={toggleFlip}
          className="px-4 py-2 rounded-lg text-sm font-medium bg-sage text-on-accent hover:bg-sage-hover transition-colors cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-peri"
        >
          {t('Flip')}
        </button>
        <button
          onClick={goNext}
          disabled={currentIndex === cards.length - 1}
          className="px-4 py-2 rounded-lg text-sm font-medium bg-surface-2 text-text border border-border hover:border-border-strong disabled:opacity-40 disabled:cursor-not-allowed transition-colors cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-peri"
        >
          {t('Next')}
        </button>
      </div>

      <p className="text-[11px] font-mono text-text-faint">
        <Kbd>{t('space')}</Kbd> {t('flip ·')} <Kbd>←</Kbd> <Kbd>→</Kbd> {t('navigate')}
      </p>
    </div>
  )
}
