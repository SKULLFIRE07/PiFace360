import axios from 'axios'

export function getCookie(name) {
  const value = `; ${document.cookie}`
  const parts = value.split(`; ${name}=`)
  if (parts.length === 2) {
    return parts.pop().split(';').shift()
  }
  return null
}

export const api = axios.create({
  baseURL: '/api',
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor: attach CSRF token on mutating requests
api.interceptors.request.use((config) => {
  const method = config.method?.toUpperCase()
  if (['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
    const csrfToken = getCookie('csrf_token')
    if (csrfToken) {
      config.headers['X-CSRF-Token'] = csrfToken
    }
  }
  return config
})

// Response interceptor: unwrap ApiResponse envelope {success, data, error}
// so that response.data gives the inner payload directly.
api.interceptors.response.use(
  (response) => {
    const body = response.data
    if (body && typeof body === 'object' && 'success' in body && 'data' in body) {
      response.data = body.data
    }
    return response
  },
  (error) => {
    if (error.response?.status === 401) {
      const currentPath = window.location.pathname
      if (currentPath !== '/login' && currentPath !== '/setup') {
        // Clear any cached query data by dispatching a custom event
        window.dispatchEvent(new CustomEvent('auth:logout'))
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)
