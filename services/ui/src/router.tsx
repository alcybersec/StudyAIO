import { createBrowserRouter } from 'react-router-dom'
import { AppLayout } from './components/layout/AppLayout'
import { CoursePage } from './pages/CoursePage'
import { DashboardPage } from './pages/DashboardPage'
import { ExamDetailPage } from './pages/ExamDetailPage'
import { ExamListPage } from './pages/ExamListPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { QAPage } from './pages/QAPage'
import { ReviewInboxPage } from './pages/ReviewInboxPage'
import { SettingsPage } from './pages/SettingsPage'
import { StudyPage } from './pages/StudyPage'
import { TimedStudyPage } from './pages/TimedStudyPage'
import { UploadPage } from './pages/UploadPage'
import { WeekViewPage } from './pages/WeekViewPage'

export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      { path: '/', element: <DashboardPage /> },
      { path: '/courses/:courseCode', element: <CoursePage /> },
      { path: '/courses/:courseCode/weeks/:weekNumber', element: <WeekViewPage /> },
      { path: '/upload', element: <UploadPage /> },
      { path: '/review', element: <ReviewInboxPage /> },
      { path: '/qa', element: <QAPage /> },
      { path: '/study', element: <StudyPage /> },
      { path: '/timed-study', element: <TimedStudyPage /> },
      { path: '/exams', element: <ExamListPage /> },
      { path: '/exams/:examId', element: <ExamDetailPage /> },
      { path: '/settings', element: <SettingsPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])
