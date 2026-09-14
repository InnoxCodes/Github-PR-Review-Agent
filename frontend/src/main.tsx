import '@/styles/index.css'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MotionConfig } from 'framer-motion'
import { lazy, StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router'
import { AppShell } from '@/components/layout/AppShell'
import { AppToaster } from '@/components/layout/AppToaster'
import { ApiError } from '@/lib/api'
import { ThemeProvider } from '@/lib/theme'
import { RouteError } from '@/pages/RouteError'

const HomePage = lazy(() => import('@/pages/HomePage'))
const ReviewsPage = lazy(() => import('@/pages/ReviewsPage'))
const ReviewPage = lazy(() => import('@/pages/ReviewPage'))
const AnalyticsPage = lazy(() => import('@/pages/AnalyticsPage'))
const ReposPage = lazy(() => import('@/pages/ReposPage'))
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage'))

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 10_000,
      refetchOnWindowFocus: false,
      // 4xx responses are answers, not glitches — retrying them only delays the error state.
      retry: (failureCount, error) => !(error instanceof ApiError && error.status >= 400 && error.status < 500) && failureCount < 2,
    },
  },
})

const router = createBrowserRouter([
  {
    path: '/',
    element: <AppShell />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'reviews', element: <ReviewsPage /> },
      { path: 'reviews/:reviewId', element: <ReviewPage /> },
      { path: 'analytics', element: <AnalyticsPage /> },
      { path: 'repos', element: <ReposPage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
])

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <MotionConfig reducedMotion="user">
          <RouterProvider router={router} />
          <AppToaster />
        </MotionConfig>
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>,
)
