import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [setupComplete, setSetupComplete] = useState(true)

  // Check auth and setup status on mount
  useEffect(() => {
    let cancelled = false

    async function checkAuth() {
      try {
        const response = await api.get('/settings')
        if (!cancelled) {
          const settings = response.data || {}
          setSetupComplete(settings.setup_complete ?? false)
          // If we got a 200, the user is authenticated
          setUser(settings.user || { username: 'admin', role: 'admin' })
        }
      } catch (err) {
        if (!cancelled) {
          if (err.response?.status === 401) {
            setUser(null)
          }
          // If settings endpoint returns setup info even without auth
          if (err.response?.data?.setup_complete !== undefined) {
            setSetupComplete(err.response.data.setup_complete)
          }
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    checkAuth()

    return () => {
      cancelled = true
    }
  }, [])

  // Listen for forced logout from the axios interceptor
  useEffect(() => {
    const handleLogout = () => {
      setUser(null)
    }
    window.addEventListener('auth:logout', handleLogout)
    return () => window.removeEventListener('auth:logout', handleLogout)
  }, [])

  const login = useCallback(async (username, password) => {
    const response = await api.post('/auth/login', { username, password })
    const userData = response.data?.user || { username, role: 'admin' }
    setUser(userData)
    if (response.data?.setup_complete !== undefined) {
      setSetupComplete(response.data.setup_complete)
    }
    return response.data
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.post('/auth/logout')
    } catch {
      // Ignore errors during logout
    } finally {
      setUser(null)
      window.location.href = '/login'
    }
  }, [])

  const value = {
    user,
    loading,
    setupComplete,
    setSetupComplete,
    login,
    logout,
    isAuthenticated: !!user,
  }

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
