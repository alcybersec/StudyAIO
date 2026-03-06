import { useNavigate } from 'react-router-dom'
import * as Dialog from '@radix-ui/react-dialog'

interface UpgradeCTAProps {
  open: boolean
  onDismiss: () => void
}

export function UpgradeCTA({ open, onDismiss }: UpgradeCTAProps) {
  const navigate = useNavigate()

  return (
    <Dialog.Root open={open} onOpenChange={(v) => !v && onDismiss()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/50" />
        <Dialog.Content className="fixed z-50 top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-surface border border-border rounded-xl shadow-xl max-w-md w-full mx-4 p-6">
          <div className="text-center">
            <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center">
              <svg className="w-6 h-6 text-amber-600 dark:text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
            </div>

            <Dialog.Title className="text-lg font-semibold text-text mb-2">
              Demo Account
            </Dialog.Title>

            <Dialog.Description className="text-sm text-text-muted mb-6">
              This action isn't available in demo mode. Create a free account to upload files, take quizzes, and save your progress.
            </Dialog.Description>

            <div className="flex gap-3">
              <button
                type="button"
                onClick={onDismiss}
                className="flex-1 px-4 py-2.5 text-sm font-medium rounded-lg border border-border text-text hover:bg-surface-alt transition-colors"
              >
                Continue Browsing
              </button>
              <button
                type="button"
                onClick={() => navigate('/register')}
                className="flex-1 px-4 py-2.5 text-sm font-medium rounded-lg bg-primary text-white hover:bg-primary/90 transition-colors"
              >
                Register
              </button>
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
