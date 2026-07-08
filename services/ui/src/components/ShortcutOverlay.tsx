import * as Dialog from '@radix-ui/react-dialog'
import { Keyboard } from 'lucide-react'
import { Kbd } from './ui/Kbd'

interface ShortcutOverlayProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

const shortcuts: Array<[string, string]> = [
  ['⌘K', 'command palette'],
  ['S', 'start session'],
  ['U', 'upload'],
  ['?', 'this overlay'],
  ['g h', 'go home'],
  ['g s', 'go study'],
  ['j / k', 'next / prev row'],
  ['a e d', 'triage inbox'],
  ['space', 'reveal card'],
  ['1–4', 'rate recall'],
]

export function ShortcutOverlay({ open, onOpenChange }: ShortcutOverlayProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
        <Dialog.Content
          className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-[calc(100vw-2rem)] max-w-md bg-surface-1 border border-border-strong rounded-xl shadow-2xl shadow-black/20 p-5 focus:outline-none"
          aria-describedby={undefined}
        >
          <div className="flex items-center gap-2 mb-4">
            <Keyboard size={15} className="text-text-faint" aria-hidden />
            <Dialog.Title className="text-sm font-semibold text-text">Keyboard shortcuts</Dialog.Title>
            <Kbd className="ml-auto">esc</Kbd>
          </div>
          <div className="grid grid-cols-2 gap-x-8 gap-y-2">
            {shortcuts.map(([key, label]) => (
              <div key={key} className="flex items-center justify-between text-[13px]">
                <span className="text-text-muted">{label}</span>
                <Kbd>{key}</Kbd>
              </div>
            ))}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
