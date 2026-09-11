import type { ReactNode } from 'react'
import { TriangleAlert } from 'lucide-react'
import { Button, Modal } from '../ui'

interface ConfirmActionProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  /** Phrased as the question being asked, e.g. "Change role to demo?" */
  title: string
  /** One entry per consequence, stated in full. Not a summary. */
  consequences: ReactNode[]
  confirmLabel: string
  onConfirm: () => void
  pending?: boolean
  error?: string | null
}

/**
 * A modal that names what an admin mutation actually does before doing it.
 *
 * There were two confirmation patterns on this surface already, and neither
 * fits these actions. `UserRowActions`' two-click swap works for deletion —
 * "delete" carries its own meaning, so a second click is enough — but it has
 * nowhere to put a paragraph. `DataPrivacySection` re-authenticates, which is
 * the right shape when you are destroying *your own* account and wrong here:
 * an admin proving their own identity says nothing about whether they picked
 * the right row out of a paginated table.
 *
 * So: state the consequences, then require a positive action. The consequences
 * are the whole point. "Are you sure?" would be worse than nothing — it teaches
 * the operator to click through a dialog that never tells them anything.
 */
export function ConfirmAction({
  open,
  onOpenChange,
  title,
  consequences,
  confirmLabel,
  onConfirm,
  pending = false,
  error = null,
}: ConfirmActionProps) {
  return (
    <Modal open={open} onOpenChange={onOpenChange} title={title}>
      <div className="space-y-3">
        <p className="flex items-start gap-2 text-xs text-red-fg">
          <TriangleAlert size={14} className="mt-px shrink-0" aria-hidden />
          <span>This takes effect immediately. There is no undo.</span>
        </p>

        <ul className="space-y-1.5 text-xs text-text-muted list-disc pl-4">
          {consequences.map((line, i) => (
            <li key={i}>{line}</li>
          ))}
        </ul>

        {error && (
          <p role="alert" className="text-xs text-red-fg">
            {error}
          </p>
        )}

        <div className="flex gap-2 pt-1">
          <Button variant="danger" size="sm" disabled={pending} onClick={onConfirm}>
            {pending ? 'Working…' : confirmLabel}
          </Button>
          <Button variant="ghost" size="sm" disabled={pending} onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
        </div>
      </div>
    </Modal>
  )
}
