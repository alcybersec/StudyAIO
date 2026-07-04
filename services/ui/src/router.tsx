import { lazy, Suspense } from 'react'
import { Navigate, Outlet, createBrowserRouter, useParams } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import { QuotaProvider } from './contexts/QuotaContext'
import { AppLayout } from './components/layout/AppLayout'
import { AuthLayout } from './components/layout/AuthLayout'
import { ProtectedRoute } from './components/auth/ProtectedRoute'
import { PublicOnlyRoute } from './components/auth/PublicOnlyRoute'
import { RouteErrorBoundary } from './components/RouteErrorBoundary'
import { LoadingSpinner } from './components/ui/LoadingSpinner'

// Lazy-loaded page components (route-level code splitting)
const AdminPage = lazy(() => import('./pages/AdminPage').then(m => ({ default: m.AdminPage })))
const AdminUserDetailPage = lazy(() => import('./pages/AdminUserDetailPage').then(m => ({ default: m.AdminUserDetailPage })))
const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage').then(m => ({ default: m.AnalyticsPage })))
const ChatPage = lazy(() => import('./pages/ChatPage').then(m => ({ default: m.ChatPage })))
const CoursePage = lazy(() => import('./pages/CoursePage').then(m => ({ default: m.CoursePage })))
const CourseOpsPage = lazy(() => import('./pages/CourseOpsPage').then(m => ({ default: m.CourseOpsPage })))
const DashboardPage = lazy(() => import('./pages/DashboardPage').then(m => ({ default: m.DashboardPage })))
const ForgotPasswordPage = lazy(() => import('./pages/ForgotPasswordPage').then(m => ({ default: m.ForgotPasswordPage })))
const LoginPage = lazy(() => import('./pages/LoginPage').then(m => ({ default: m.LoginPage })))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage').then(m => ({ default: m.NotFoundPage })))
const ProfilePage = lazy(() => import('./pages/ProfilePage').then(m => ({ default: m.ProfilePage })))
const QAPage = lazy(() => import('./pages/QAPage').then(m => ({ default: m.QAPage })))
const RegisterPage = lazy(() => import('./pages/RegisterPage').then(m => ({ default: m.RegisterPage })))
const ResetPasswordPage = lazy(() => import('./pages/ResetPasswordPage').then(m => ({ default: m.ResetPasswordPage })))
const ReviewInboxPage = lazy(() => import('./pages/ReviewInboxPage').then(m => ({ default: m.ReviewInboxPage })))
const SettingsPage = lazy(() => import('./pages/SettingsPage').then(m => ({ default: m.SettingsPage })))
const StudyHubPage = lazy(() => import('./pages/StudyHubPage').then(m => ({ default: m.StudyHubPage })))
const AchievementsPage = lazy(() => import('./pages/AchievementsPage').then(m => ({ default: m.AchievementsPage })))
const KnowledgeGraphPage = lazy(() => import('./pages/KnowledgeGraphPage').then(m => ({ default: m.KnowledgeGraphPage })))
const UploadPage = lazy(() => import('./pages/UploadPage').then(m => ({ default: m.UploadPage })))
const WeekViewPage = lazy(() => import('./pages/WeekViewPage').then(m => ({ default: m.WeekViewPage })))

// eslint-disable-next-line react-refresh/only-export-components
function SuspenseOutlet() {
  return (
    <Suspense fallback={<LoadingSpinner size="lg" label="Loading..." />}>
      <Outlet />
    </Suspense>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
function RootLayout() {
  return (
    <AuthProvider>
      <QuotaProvider>
        <Outlet />
      </QuotaProvider>
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
              {
                element: <SuspenseOutlet />,
                errorElement: <RouteErrorBoundary />,
                children: [
                  { path: '/login', element: <LoginPage /> },
                  { path: '/register', element: <RegisterPage /> },
                  { path: '/forgot-password', element: <ForgotPasswordPage /> },
                  { path: '/reset-password', element: <ResetPasswordPage /> },
                ],
              },
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
            errorElement: <RouteErrorBoundary />,
            children: [
              {
                // Pathless wrapper: errors from any page render the boundary
                // inside AppLayout's Outlet, keeping the shell nav alive.
                errorElement: <RouteErrorBoundary />,
                children: [
              { path: '/', element: <DashboardPage /> },
              { path: '/courses/:courseCode', element: <CoursePage /> },
              { path: '/courses/:courseCode/weeks/:weekNumber', element: <WeekViewPage /> },
              { path: '/courses/:courseCode/ops', element: <CourseOpsPage /> },
              { path: '/upload', element: <UploadPage /> },
              { path: '/review', element: <ReviewInboxPage /> },
              { path: '/qa', element: <QAPage /> },
              { path: '/analytics', element: <AnalyticsPage /> },
              { path: '/study', element: <StudyHubPage /> },
              { path: '/chat', element: <ChatPage /> },
              // Redirects from old routes
              { path: '/timed-study', element: <Navigate to="/study?tab=timed" replace /> },
              { path: '/exams', element: <Navigate to="/study?tab=exams" replace /> },
              { path: '/exams/:examId', element: <ExamRedirect /> },
              { path: '/knowledge', element: <KnowledgeGraphPage /> },
              { path: '/achievements', element: <AchievementsPage /> },
              { path: '/admin', element: <AdminPage /> },
              { path: '/admin/users/:userId', element: <AdminUserDetailPage /> },
              { path: '/settings', element: <SettingsPage /> },
              { path: '/profile', element: <ProfilePage /> },
              { path: '*', element: <NotFoundPage /> },
                ],
              },
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
