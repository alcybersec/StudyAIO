import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'

export function PublicOnlyRoute() {
  const { isAuthenticated, isSelfHosted } = useAuth()

  if (!isSelfHosted && isAuthenticated) {
    return <Navigate to="/" replace />
  }

  return <Outlet />
}
