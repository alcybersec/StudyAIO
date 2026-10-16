/** Marks the root of an AiFeedbackControl so a screen's global shortcuts can leave it alone. */
export const AI_FEEDBACK_ATTR = 'data-ai-feedback'

/**
 * True when a key event came from inside a feedback control. Study screens bind
 * Space, Enter, digits and `p` on the window; without this check, pressing Enter
 * on a thumb flips the card instead, and typing a reason rates it.
 */
export function isFromAiFeedback(target: EventTarget | null): boolean {
  return target instanceof Element && target.closest(`[${AI_FEEDBACK_ATTR}]`) !== null
}
