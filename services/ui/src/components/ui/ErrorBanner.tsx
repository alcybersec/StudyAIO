interface ErrorBannerProps {
  message?: string
  onRetry?: () => void
}

export function ErrorBanner({ message = 'Something went wrong', onRetry }: ErrorBannerProps) {
  return (
    <div className="rounded-xl border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950 p-4 flex items-center justify-between gap-4">
      <div className="flex items-center gap-3 min-w-0">
        <span className="flex-shrink-0 w-8 h-8 rounded-full bg-red-100 dark:bg-red-900 text-red-600 dark:text-red-400 flex items-center justify-center text-sm font-bold">
          !
        </span>
        <p className="text-sm text-red-800 dark:text-red-300 truncate">{message}</p>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex-shrink-0 px-4 py-2.5 min-h-[44px] rounded-lg text-sm font-medium bg-red-600 text-white hover:bg-red-700 transition-colors"
        >
          Retry
        </button>
      )}
    </div>
  )
}
