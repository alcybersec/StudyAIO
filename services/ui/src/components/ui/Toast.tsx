import { Toaster as SonnerToaster } from 'sonner'

export function Toaster() {
  return (
    <SonnerToaster
      position="bottom-right"
      toastOptions={{
        className: 'bg-surface text-text border-border',
        duration: 4000,
      }}
      richColors
      closeButton
    />
  )
}
