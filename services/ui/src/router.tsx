import { Navigate, Outlet, createBrowserRouter, useParams } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import { AppLayout } from './components/layout/AppLayout'
import { AuthLayout } from './components/layout/AuthLayout'
import { ProtectedRoute } from './components/auth/ProtectedRoute'
import { PublicOnlyRoute } from './components/auth/PublicOnlyRoute'
import { CoursePage } from './pages/CoursePage'
import { CourseOpsPage } from './pages/CourseOpsPage'
import { DashboardPage } from './pages/DashboardPage'
import { ForgotPasswordPage } from './pages/ForgotPasswordPage'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { ProfilePage } from './pages/ProfilePage'
import { QAPage } from './pages/QAPage'
import { RegisterPage } from './pages/RegisterPage'
import { ResetPasswordPage } from './pages/ResetPasswordPage'
import { ReviewInboxPage } from './pages/ReviewInboxPage'
import { SettingsPage } from './pages/SettingsPage'
import { StudyHubPage } from './pages/StudyHubPage'
import { UploadPage } from './pages/UploadPage'
import { WeekViewPage } from './pages/WeekViewPage'

// eslint-disable-next-line react-refresh/only-export-components
function RootLayout() {
  return (
    <AuthProvider>
      <Outlet />
    </AuthProvider>
  )
}

export const router = createBrowserRouter([
  {
    element: <RootLayout />,
    children: [
      // Public auth routes (redirect to / if already authenticated)
      {
        element: <PublicOnlyRoute />,
        children: [
          {
            element: <AuthLayout />,
            children: [
              { path: '/login', element: <LoginPage /> },
              { path: '/register', element: <RegisterPage /> },
              { path: '/forgot-password', element: <ForgotPasswordPage /> },
              { path: '/reset-password', element: <ResetPasswordPage /> },
            ],
          },
        ],
      },
      // Protected app routes (redirect to /login if not authenticated)
      {
        element: <ProtectedRoute />,
        children: [
          {
            element: <AppLayout />,
            children: [
              { path: '/', element: <DashboardPage /> },
              { path: '/courses/:courseCode', element: <CoursePage /> },
              { path: '/courses/:courseCode/weeks/:weekNumber', element: <WeekViewPage /> },
              { path: '/courses/:courseCode/ops', element: <CourseOpsPage /> },
              { path: '/upload', element: <UploadPage /> },
              { path: '/review', element: <ReviewInboxPage /> },
              { path: '/qa', element: <QAPage /> },
              { path: '/study', element: <StudyHubPage /> },
              // Redirects from old routes
              { path: '/timed-study', element: <Navigate to="/study?tab=timed" replace /> },
              { path: '/exams', element: <Navigate to="/study?tab=exams" replace /> },
              { path: '/exams/:examId', element: <ExamRedirect /> },
              { path: '/settings', element: <SettingsPage /> },
              { path: '/profile', element: <ProfilePage /> },
              { path: '*', element: <NotFoundPage /> },
            ],
          },
        ],
      },
    ],
  },
])

// eslint-disable-next-line react-refresh/only-export-components
function ExamRedirect() {
  const { examId } = useParams<{ examId: string }>()
  return <Navigate to={`/study?tab=exams&exam=${examId}`} replace />
}
