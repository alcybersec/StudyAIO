interface OAuthButtonsProps {
  providers: string[]
}

const providerLabels: Record<string, string> = {
  google: 'Google',
  github: 'GitHub',
}

export function OAuthButtons({ providers }: OAuthButtonsProps) {
  if (providers.length === 0) return null

  return (
    <div className="space-y-2">
      <div className="relative my-4">
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-gray-200" />
        </div>
        <div className="relative flex justify-center text-sm">
          <span className="bg-white px-2 text-gray-400">or continue with</span>
        </div>
      </div>
      {providers.map((provider) => (
        <button
          key={provider}
          type="button"
          className="w-full flex items-center justify-center gap-2 px-4 min-h-[44px] rounded-lg border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
          onClick={() => {
            window.location.href = `/api/auth/oauth/${provider}`
          }}
        >
          {providerLabels[provider] ?? provider}
        </button>
      ))}
    </div>
  )
}
