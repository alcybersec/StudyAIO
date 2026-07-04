import { QueryClient, QueryClientProvider, onlineManager } from '@tanstack/react-query'
import { RouterProvider } from 'react-router-dom'
import { shouldRetryQuery } from './lib/queryRetry'
import { router } from './router'

// Drive React Query's online state from the browser connectivity events so
// paused queries resume (and refetch) the moment the connection returns.
onlineManager.setEventListener((setOnline) => {
  const onOnline = () => setOnline(true)
  const onOffline = () => setOnline(false)
  window.addEventListener('online', onOnline)
  window.addEventListener('offline', onOffline)
  return () => {
    window.removeEventListener('online', onOnline)
    window.removeEventListener('offline', onOffline)
  }
})

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: shouldRetryQuery,
      refetchOnReconnect: 'always',
    },
  },
})

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  )
}
