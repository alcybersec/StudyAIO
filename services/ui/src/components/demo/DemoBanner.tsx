import { Link } from 'react-router-dom'

export function DemoBanner() {
  return (
    <div className="bg-amber-500 text-white text-center text-sm py-2 px-4 flex items-center justify-center gap-3 sticky top-0 z-50">
      <span>You're using a demo account — changes won't be saved.</span>
      <Link
        to="/register"
        className="inline-flex items-center px-3 py-1 rounded-md bg-white text-amber-600 text-xs font-semibold hover:bg-amber-50 transition-colors"
      >
        Sign up free
      </Link>
    </div>
  )
}
