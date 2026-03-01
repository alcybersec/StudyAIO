import { createBrowserRouter } from 'react-router-dom'
import { AppLayout } from './components/layout/AppLayout'
import { CoursePage } from './pages/CoursePage'
import { DashboardPage } from './pages/DashboardPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { QAPage } from './pages/QAPage'
import { ReviewInboxPage } from './pages/ReviewInboxPage'
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
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])
