import { createBrowserRouter } from 'react-router-dom'
import { AppLayout } from './components/layout/AppLayout'
import { CoursePage } from './pages/CoursePage'
import { DashboardPage } from './pages/DashboardPage'
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
    ],
  },
])
