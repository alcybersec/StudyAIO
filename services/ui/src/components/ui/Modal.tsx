import type { ReactNode } from 'react'
import * as Dialog from '@radix-ui/react-dialog'
import { X } from 'lucide-react'

interface ModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: ReactNode
  description?: ReactNode
  children: ReactNode
  className?: string
}

export function Modal({ open, onOpenChange, title, description, children, className = '' }: ModalProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
        <Dialog.Content
          className={`fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-[calc(100vw-2rem)] max-w-md bg-surface-1 border border-border-strong rounded-xl shadow-2xl shadow-black/20 p-5 focus:outline-none ${className}`}
        >
          <div className="flex items-start justify-between gap-4 mb-3">
            <div>
              <Dialog.Title className="text-sm font-semibold text-text">{title}</Dialog.Title>
              {description && (
                <Dialog.Description className="text-xs text-text-muted mt-1">
                  {description}
                </Dialog.Description>
              )}
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label="Close"
                className="shrink-0 -m-1 p-1 rounded-md text-text-faint hover:text-text hover:bg-surface-2 cursor-pointer"
              >
                <X size={14} aria-hidden />
              </button>
            </Dialog.Close>
          </div>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
