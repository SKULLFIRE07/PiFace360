import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { CheckCircle2, Loader2 } from 'lucide-react'
import { api } from '../../api/client'
import { useAuth } from '../../hooks/useAuth'

export default function CompleteStep() {
  const navigate = useNavigate()
  const { setSetupComplete } = useAuth()
  const [settings, setSettings] = useState(null)
  const [loading, setLoading] = useState(false)
  const [apiError, setApiError] = useState('')

  useEffect(() => {
    async function fetchSummary() {
      try {
        const res = await api.get('/setup/summary')
        setSettings(res.data)
      } catch {
        // Non-critical: summary display is optional
      }
    }
    fetchSummary()
  }, [])

  async function handleFinish() {
    setLoading(true)
    setApiError('')
    try {
      await api.post('/setup/complete', { setup_complete: true })
      setSetupComplete(true)
      navigate('/today', { replace: true })
    } catch (err) {
      setApiError(err.response?.data?.detail || 'Failed to finalize setup.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card text-center">
      <div className="flex justify-center mb-4">
        <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center">
          <CheckCircle2 className="w-10 h-10 text-green-600" />
        </div>
      </div>

      <h2 className="text-xl font-bold text-gray-900 mb-2">Setup Complete!</h2>
      <p className="text-gray-600 mb-6">Your attendance system is ready.</p>

      {settings && (
        <div className="text-left mb-6 p-4 bg-gray-50 rounded-lg space-y-3">
          <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
            Configuration Summary
          </h3>
          {settings.company_name && (
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Company</span>
              <span className="font-medium text-gray-900">{settings.company_name}</span>
            </div>
          )}
          {settings.shift_start && (
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Shift Start</span>
              <span className="font-medium text-gray-900">{settings.shift_start}</span>
            </div>
          )}
          {settings.shift_end && (
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Shift End</span>
              <span className="font-medium text-gray-900">{settings.shift_end}</span>
            </div>
          )}
          {settings.late_threshold_minutes != null && (
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Late Threshold</span>
              <span className="font-medium text-gray-900">
                {settings.late_threshold_minutes} minutes
              </span>
            </div>
          )}
          {settings.weekend_days && settings.weekend_days.length > 0 && (
            <div className="flex justify-between text-sm">
              <span className="text-gray-500">Off Days</span>
              <span className="font-medium text-gray-900 capitalize">
                {settings.weekend_days.join(', ')}
              </span>
            </div>
          )}
          <div className="flex justify-between text-sm">
            <span className="text-gray-500">Calibration</span>
            <span className="font-medium text-green-600">Configured</span>
          </div>
        </div>
      )}

      {apiError && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {apiError}
        </div>
      )}

      <button onClick={handleFinish} className="btn-primary w-full sm:w-auto" disabled={loading}>
        {loading ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin mr-2" />
            Finalizing...
          </>
        ) : (
          'Go to Dashboard'
        )}
      </button>
    </div>
  )
}
