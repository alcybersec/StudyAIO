import * as Dialog from '@radix-ui/react-dialog'
import { AnimatePresence, motion } from 'motion/react'
import type { ReactNode } from 'react'

interface SheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  children: ReactNode
  side?: 'bottom' | 'right'
  /**
   * Accessible name for the sheet. Rendered as a visible heading; pass
   * `titleVisible={false}` to keep it screen-reader-only. Radix requires a
   * Dialog.Title on every dialog, so this is effectively mandatory for a11y —
   * callers without a visible header must still supply one for screen readers.
   */
  title: string
  titleVisible?: boolean
}

const slideVariants = {
  bottom: {
    hidden: { y: '100%' },
    visible: { y: 0 },
  },
  right: {
    hidden: { x: '100%' },
    visible: { x: 0 },
  },
}

const positionClasses = {
  bottom: 'inset-x-0 bottom-0 rounded-t-2xl max-h-[85vh]',
  right: 'inset-y-0 right-0 w-80 max-w-[90vw]',
}

export function Sheet({
  open,
  onOpenChange,
  children,
  side = 'bottom',
  title,
  titleVisible = true,
}: SheetProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <AnimatePresence>
        {open && (
          <Dialog.Portal forceMount>
            <Dialog.Overlay asChild>
              <motion.div
                className="fixed inset-0 z-50 bg-black/40"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
              />
            </Dialog.Overlay>
            <Dialog.Content asChild>
              <motion.div
                className={`fixed z-50 bg-surface-1 border-border shadow-lg overflow-y-auto ${positionClasses[side]}`}
                variants={slideVariants[side]}
                initial="hidden"
                animate="visible"
                exit="hidden"
                transition={{ type: 'spring', damping: 30, stiffness: 300 }}
              >
                {side === 'bottom' && (
                  <div className="flex justify-center pt-3 pb-1">
                    <div className="w-10 h-1 rounded-full bg-border-strong" />
                  </div>
                )}
                <Dialog.Title
                  className={
                    titleVisible ? 'px-4 pt-2 pb-3 text-lg font-semibold text-text' : 'sr-only'
                  }
                >
                  {title}
                </Dialog.Title>
                <div className="p-4">{children}</div>
              </motion.div>
            </Dialog.Content>
          </Dialog.Portal>
        )}
      </AnimatePresence>
    </Dialog.Root>
  )
}
