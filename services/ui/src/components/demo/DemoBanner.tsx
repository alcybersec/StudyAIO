import { Link } from 'react-router-dom'

export function DemoBanner() {
  return (
    <div className="bg-amber text-on-accent text-center text-sm py-2 px-4 flex items-center justify-center gap-3 sticky top-0 z-50">
      <span>You're using a demo account — changes won't be saved.</span>
      <Link
        to="/register"
        className="inline-flex items-center px-3 py-1 rounded-md bg-on-accent text-amber text-xs font-semibold hover:opacity-90 transition-colors"
      >
        Sign up free
      </Link>
    </div>
  )
}
