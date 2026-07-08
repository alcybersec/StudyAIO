import { toast } from 'sonner'
import {
  AppApiError,
  NetworkError,
  NotFoundError,
  RateLimitError,
  ServerError,
  ValidationError,
} from '../api/errors'

export interface ToastContent {
  message: string
  description?: string
}

/**
 * Pure mapping from the error taxonomy to plain-language toast content.
 * Never surfaces raw error strings — full detail stays behind ErrorState
 * expanders, toasts stay human.
 */
export function mutationErrorContent(err: unknown): ToastContent {
  if (err instanceof ValidationError) {
    const fieldMessages = Object.values(err.fields)
    return {
      message: fieldMessages[0] ?? err.message,
      description: fieldMessages.length > 1 ? 'Check the highlighted fields.' : undefined,
    }
  }
  if (err instanceof NotFoundError) {
    return {
      message: err.message,
      description: 'It may have been removed — this item no longer exists.',
    }
  }
  if (err instanceof RateLimitError) {
    return {
      message: `Rate limited — try again in ${err.retryAfterSeconds}s`,
    }
  }
  if (err instanceof NetworkError) {
    return {
      message: "Couldn't reach the server",
      description: 'Check your connection — your work is kept locally where possible.',
    }
  }
  if (err instanceof ServerError) {
    return {
      message: 'The server hit a problem',
      description: 'Nothing you did — a retry usually fixes it.',
    }
  }
  if (err instanceof AppApiError) {
    return { message: err.message }
  }
  return { message: 'Something went wrong', description: 'Please try again.' }
}

/**
 * Show a mutation-failure toast with a Retry action.
 * Rate-limit errors show a live countdown instead of an immediate retry.
 */
export function toastMutationError(err: unknown, retryFn?: () => void): void {
  if (err instanceof RateLimitError) {
    let remaining = err.retryAfterSeconds
    const id = toast.error(`Rate limited — try again in ${remaining}s`, {
      duration: remaining * 1_000,
    })
    const interval = setInterval(() => {
      remaining -= 1
      if (remaining <= 0) {
        clearInterval(interval)
        toast.error('You can retry now', {
          id,
          duration: 5_000,
          action: retryFn ? { label: 'Retry', onClick: retryFn } : undefined,
        })
        return
      }
      toast.error(`Rate limited — try again in ${remaining}s`, { id })
    }, 1_000)
    return
  }

  const { message, description } = mutationErrorContent(err)
  toast.error(message, {
    description,
    action: retryFn ? { label: 'Retry', onClick: retryFn } : undefined,
  })
}
