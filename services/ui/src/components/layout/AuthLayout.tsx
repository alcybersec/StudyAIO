import { Outlet } from 'react-router-dom'

export function AuthLayout() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-primary">StudyAIO</h1>
          <p className="mt-2 text-sm text-gray-500">AI-powered study workspace</p>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-6">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
