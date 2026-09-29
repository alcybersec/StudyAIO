import * as Dialog from '@radix-ui/react-dialog'
import { useTranslation } from 'react-i18next'
import { Keyboard } from 'lucide-react'
import { Kbd } from './ui/Kbd'

interface ShortcutOverlayProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

//: Objects rather than tuples so the descriptions are collected as
//: translation keys — a tuple's second element looks like nothing in
//: particular to the key generator, and these sat untranslated because of it.
const shortcuts: Array<{ keys: string; label: string }> = [
  { keys: '⌘K', label: 'command palette' },
  { keys: 'S', label: 'start session' },
  { keys: 'U', label: 'upload' },
  { keys: '?', label: 'this overlay' },
  { keys: 'g h', label: 'go home' },
  { keys: 'g s', label: 'go study' },
  { keys: 'j / k', label: 'next / prev row' },
  { keys: 'a e d', label: 'triage inbox' },
  { keys: 'space', label: 'reveal card' },
  { keys: '1–4', label: 'rate recall' },
]

export function ShortcutOverlay({ open, onOpenChange }: ShortcutOverlayProps) {
  const { t } = useTranslation()

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
            <Dialog.Title className="text-sm font-semibold text-text">{t('Keyboard shortcuts')}</Dialog.Title>
            <Kbd className="ml-auto">{t('esc')}</Kbd>
          </div>
          <div className="grid grid-cols-2 gap-x-8 gap-y-2">
            {shortcuts.map(({ keys, label }) => (
              <div key={keys} className="flex items-center justify-between text-[13px]">
                <span className="text-text-muted">{t(label)}</span>
                <Kbd>{keys}</Kbd>
              </div>
            ))}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
