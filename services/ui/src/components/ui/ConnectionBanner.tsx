interface ConnectionBannerProps {
  connected: boolean
}

export function ConnectionBanner({ connected }: ConnectionBannerProps) {
  if (connected) return null

  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 flex items-center gap-3">
      <span className="flex-shrink-0 w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
      <p className="text-sm text-amber-800">
        Live updates disconnected. Pipeline progress may be delayed.
      </p>
    </div>
  )
}
