import { useMemo } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import i18n from '../i18n'
import { aiFeedbackApi } from '../api/aiFeedback'
import { NotFoundError } from '../api/errors'
import type { AIFeedbackReason, AIFeedbackTargetType, AIFeedbackVote } from '../types'

/** The server caps one lookup at 100 ids. */
const MAX_BATCH = 100

export interface VoteDraft {
  rating: 1 | -1
  reason?: AIFeedbackReason
  comment?: string
}

interface MutationInput {
  targetId: string
  /** null clears the caller's vote. */
  draft: VoteDraft | null
}

/**
 * The caller's votes for one view's worth of AI items, plus optimistic
 * set/clear. Items sharing a `ids` list share one batched request and one
 * cache entry, so a screen of twenty cards costs one GET.
 */
export function useAiFeedback(targetType: AIFeedbackTargetType, ids: string[]) {
  const queryClient = useQueryClient()
  const batch = useMemo(() => [...new Set(ids)].sort().slice(0, MAX_BATCH), [ids])
  const key = useMemo(() => ['ai-feedback', targetType, batch.join(',')], [targetType, batch])

  const query = useQuery({
    queryKey: key,
    queryFn: () => aiFeedbackApi.mine(targetType, batch),
    enabled: batch.length > 0,
    staleTime: 60_000,
  })

  const mutation = useMutation({
    mutationFn: async ({ targetId, draft }: MutationInput) => {
      if (draft === null) {
        try {
          await aiFeedbackApi.clear(targetType, targetId)
        } catch (err) {
          // Nothing to clear is the state the user asked for.
          if (!(err instanceof NotFoundError)) throw err
        }
        return
      }
      await aiFeedbackApi.put({
        target_type: targetType,
        target_id: targetId,
        rating: draft.rating,
        ...(draft.reason ? { reason: draft.reason } : {}),
        ...(draft.comment ? { comment: draft.comment } : {}),
      })
    },
    onMutate: async ({ targetId, draft }) => {
      await queryClient.cancelQueries({ queryKey: key })
      const previous = queryClient.getQueryData<AIFeedbackVote[]>(key)
      queryClient.setQueryData<AIFeedbackVote[]>(key, (old = []) => {
        const rest = old.filter((v) => v.target_id !== targetId)
        if (draft === null) return rest
        return [
          ...rest,
          {
            target_type: targetType,
            target_id: targetId,
            rating: draft.rating,
            reason: draft.reason ?? null,
            comment: draft.comment ?? null,
          },
        ]
      })
      return { previous }
    },
    onError: (err, vars, context) => {
      queryClient.setQueryData(key, context?.previous)
      if (vars.draft !== null && err instanceof NotFoundError) {
        // Archived or removed since it was shown: retrying cannot help.
        toast.info(i18n.t('This item was archived, so it can no longer be rated.'))
        return
      }
      toast.error(i18n.t("Couldn't save your feedback. Please try again."))
    },
  })

  const votes = useMemo(() => {
    const map = new Map<string, AIFeedbackVote>()
    for (const v of query.data ?? []) map.set(v.target_id, v)
    return map
  }, [query.data])

  return {
    votes,
    isPending: mutation.isPending,
    vote: (targetId: string, draft: VoteDraft | null) => mutation.mutate({ targetId, draft }),
  }
}
