import { Outlet } from 'react-router-dom'

export function AuthLayout() {
  return (
    <div className="min-h-screen bg-surface-alt flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-primary">StudyAIO</h1>
          <p className="mt-2 text-sm text-text-muted">AI-powered study workspace</p>
        </div>
        <div className="bg-surface rounded-lg border border-border shadow-sm p-6">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
