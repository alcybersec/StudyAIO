import type { ReactNode } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { X } from 'lucide-react'

interface ViewOriginalModalProps {
  open: boolean
  onClose: () => void
  children: ReactNode
}

/** Fullscreen mobile wrapper around the viewer body. */
export function ViewOriginalModal({ open, onClose, children }: ViewOriginalModalProps) {
  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/50" />
        <Dialog.Content className="fixed inset-0 z-50 flex flex-col bg-surface-0 focus:outline-none">
          <Dialog.Title className="sr-only">View original document</Dialog.Title>

          <div className="flex items-center justify-end px-2 py-1.5 border-b border-border bg-surface-1 shrink-0">
            <Dialog.Close asChild>
              <button
                className="p-2 rounded-lg hover:bg-surface-2 transition-colors min-w-[44px] min-h-[44px] flex items-center justify-center text-text-muted"
                aria-label="Close viewer"
              >
                <X size={18} aria-hidden />
              </button>
            </Dialog.Close>
          </div>

          <div className="flex-1 overflow-hidden">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
