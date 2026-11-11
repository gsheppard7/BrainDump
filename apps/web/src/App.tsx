import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'

import { ApiError } from './api'
import { Layout } from './components/Layout'
import { AskPage } from './pages/AskPage'
import { BrainPage } from './pages/BrainPage'
import { CapturePage } from './pages/CapturePage'
import { LibraryPage } from './pages/LibraryPage'
import { SourcePage } from './pages/SourcePage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (count, error) => !(error instanceof ApiError && error.status >= 400 && error.status < 500) && count < 2,
      refetchOnWindowFocus: true,
    },
  },
})

function NotFound() {
  return (
    <div className="py-16 text-center">
      <p className="text-lg font-medium">Page not found</p>
      <Link to="/" className="mt-2 inline-block text-sm text-indigo-600 hover:underline">
        Go to Capture
      </Link>
    </div>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<CapturePage />} />
            <Route path="ask" element={<AskPage />} />
            <Route path="brain" element={<BrainPage />} />
            <Route path="library" element={<LibraryPage />} />
            <Route path="sources/:id" element={<SourcePage />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
