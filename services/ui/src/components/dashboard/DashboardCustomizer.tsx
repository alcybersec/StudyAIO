import * as Dialog from '@radix-ui/react-dialog'
import { widgets } from './WidgetRegistry'

interface DashboardCustomizerProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  hiddenWidgets: string[]
  onToggle: (key: string) => void
  onReset: () => void
}

export function DashboardCustomizer({
  open,
  onOpenChange,
  hiddenWidgets,
  onToggle,
  onReset,
}: DashboardCustomizerProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/40 z-50" />
        <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 bg-surface-1 border border-border rounded-xl shadow-lg w-full max-w-sm p-6">
          <Dialog.Title className="text-lg font-semibold text-text mb-4">
            Customize Dashboard
          </Dialog.Title>

          <div className="space-y-2 mb-6">
            {widgets.map((w) => (
              <label
                key={w.key}
                className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-surface-2 transition-colors cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={!hiddenWidgets.includes(w.key)}
                  onChange={() => onToggle(w.key)}
                  className="rounded border-border text-sage focus:ring-sage"
                />
                <span className="text-sm text-text">{w.label}</span>
              </label>
            ))}
          </div>

          <div className="flex items-center justify-between">
            <button
              onClick={onReset}
              className="text-sm text-text-muted hover:text-text transition-colors"
            >
              Reset to default
            </button>
            <Dialog.Close className="px-4 py-2 text-sm font-medium rounded-lg bg-sage text-on-accent hover:bg-sage-hover transition-colors">
              Done
            </Dialog.Close>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
