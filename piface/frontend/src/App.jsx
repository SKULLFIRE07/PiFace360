import React, { lazy, Suspense } from 'react'
import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { AuthProvider, useAuth } from './hooks/useAuth'
import AppShell from './components/Layout/AppShell'
import Login from './pages/Login'
import Setup from './pages/Setup/index'

const Today = lazy(() => import('./pages/Today'))
const Employees = lazy(() => import('./pages/Employees'))
const Unknowns = lazy(() => import('./pages/Unknowns'))
const AttendanceLog = lazy(() => import('./pages/AttendanceLog'))
const Reports = lazy(() => import('./pages/Reports'))
const Settings = lazy(() => import('./pages/Settings'))
const Leave = lazy(() => import('./pages/Leave'))
const Cameras = lazy(() => import('./pages/Cameras'))

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center h-screen">
      <div className="w-8 h-8 border-4 border-primary-200 border-t-primary-600 rounded-full animate-spin" />
    </div>
  )
}

function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return <LoadingSpinner />
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return children
}

function SetupGuard({ children }) {
  const { setupComplete, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return <LoadingSpinner />
  }

  if (!setupComplete && !location.pathname.startsWith('/setup')) {
    return <Navigate to="/setup/company" replace />
  }

  return children
}

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex items-center justify-center h-screen p-4">
          <div className="card max-w-md w-full text-center">
            <h2 className="text-xl font-semibold text-gray-900 mb-2">Something went wrong</h2>
            <p className="text-gray-600 mb-4">{this.state.error?.message || 'An unexpected error occurred.'}</p>
            <button
              className="btn-primary"
              onClick={() => {
                this.setState({ hasError: false, error: null })
                window.location.href = '/'
              }}
            >
              Reload Application
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

function AppRoutes() {
  const { setupComplete, loading } = useAuth()

  if (loading) {
    return <LoadingSpinner />
  }

  return (
    <Suspense fallback={<LoadingSpinner />}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/setup/*" element={<Setup />} />

        <Route
          path="/"
          element={
            <SetupGuard>
              <ProtectedRoute>
                <Navigate to="/today" replace />
              </ProtectedRoute>
            </SetupGuard>
          }
        />

        {[
          { path: '/today', element: <Today /> },
          { path: '/employees', element: <Employees /> },
          { path: '/unknowns', element: <Unknowns /> },
          { path: '/attendance', element: <AttendanceLog /> },
          { path: '/reports', element: <Reports /> },
          { path: '/settings', element: <Settings /> },
          { path: '/leave', element: <Leave /> },
          { path: '/cameras', element: <Cameras /> },
        ].map(({ path, element }) => (
          <Route
            key={path}
            path={path}
            element={
              <SetupGuard>
                <ProtectedRoute>
                  <AppShell>{element}</AppShell>
                </ProtectedRoute>
              </SetupGuard>
            }
          />
        ))}

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  )
}

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </ErrorBoundary>
  )
}
