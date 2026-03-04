import { Outlet, createBrowserRouter } from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import { AppLayout } from './components/layout/AppLayout'
import { AuthLayout } from './components/layout/AuthLayout'
import { ProtectedRoute } from './components/auth/ProtectedRoute'
import { PublicOnlyRoute } from './components/auth/PublicOnlyRoute'
import { CoursePage } from './pages/CoursePage'
import { CourseOpsPage } from './pages/CourseOpsPage'
import { DashboardPage } from './pages/DashboardPage'
import { ExamDetailPage } from './pages/ExamDetailPage'
import { ExamListPage } from './pages/ExamListPage'
import { ForgotPasswordPage } from './pages/ForgotPasswordPage'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { ProfilePage } from './pages/ProfilePage'
import { QAPage } from './pages/QAPage'
import { RegisterPage } from './pages/RegisterPage'
import { ResetPasswordPage } from './pages/ResetPasswordPage'
import { ReviewInboxPage } from './pages/ReviewInboxPage'
import { SettingsPage } from './pages/SettingsPage'
import { StudyPage } from './pages/StudyPage'
import { TimedStudyPage } from './pages/TimedStudyPage'
import { UploadPage } from './pages/UploadPage'
import { WeekViewPage } from './pages/WeekViewPage'

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
              { path: '/study', element: <StudyPage /> },
              { path: '/timed-study', element: <TimedStudyPage /> },
              { path: '/exams', element: <ExamListPage /> },
              { path: '/exams/:examId', element: <ExamDetailPage /> },
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
