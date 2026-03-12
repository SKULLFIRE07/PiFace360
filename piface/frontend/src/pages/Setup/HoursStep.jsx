import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Clock, Loader2 } from 'lucide-react'
import { api } from '../../api/client'

const DAYS_OF_WEEK = [
  { value: 'monday', label: 'Mon' },
  { value: 'tuesday', label: 'Tue' },
  { value: 'wednesday', label: 'Wed' },
  { value: 'thursday', label: 'Thu' },
  { value: 'friday', label: 'Fri' },
  { value: 'saturday', label: 'Sat' },
  { value: 'sunday', label: 'Sun' },
]

export default function HoursStep() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    shiftStart: '09:00',
    shiftEnd: '18:00',
    lateThreshold: 15,
    weekendDays: ['saturday', 'sunday'],
  })
  const [loading, setLoading] = useState(false)
  const [apiError, setApiError] = useState('')

  function handleChange(field) {
    return (e) => {
      setForm((prev) => ({ ...prev, [field]: e.target.value }))
    }
  }

  function toggleWeekendDay(day) {
    setForm((prev) => ({
      ...prev,
      weekendDays: prev.weekendDays.includes(day)
        ? prev.weekendDays.filter((d) => d !== day)
        : [...prev.weekendDays, day],
    }))
  }

  async function handleNext(e) {
    e.preventDefault()
    setLoading(true)
    setApiError('')
    try {
      await api.post('/setup/hours', {
        shift_start: form.shiftStart,
        shift_end: form.shiftEnd,
        late_threshold_minutes: parseInt(form.lateThreshold, 10),
        weekend_days: form.weekendDays,
      })
      navigate('/setup/calibration')
    } catch (err) {
      setApiError(err.response?.data?.detail || 'Failed to save working hours.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 bg-primary-100 rounded-lg flex items-center justify-center">
          <Clock className="w-5 h-5 text-primary-600" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Working Hours</h2>
          <p className="text-sm text-gray-500">Configure shift times and late thresholds</p>
        </div>
      </div>

      {apiError && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {apiError}
        </div>
      )}

      <form onSubmit={handleNext} className="space-y-5">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label htmlFor="shiftStart" className="label">
              Shift Start Time
            </label>
            <input
              id="shiftStart"
              type="time"
              value={form.shiftStart}
              onChange={handleChange('shiftStart')}
              className="input"
              disabled={loading}
            />
          </div>
          <div>
            <label htmlFor="shiftEnd" className="label">
              Shift End Time
            </label>
            <input
              id="shiftEnd"
              type="time"
              value={form.shiftEnd}
              onChange={handleChange('shiftEnd')}
              className="input"
              disabled={loading}
            />
          </div>
        </div>

        <div>
          <label htmlFor="lateThreshold" className="label">
            Late Threshold (minutes)
          </label>
          <input
            id="lateThreshold"
            type="number"
            min="0"
            max="120"
            value={form.lateThreshold}
            onChange={handleChange('lateThreshold')}
            className="input max-w-32"
            disabled={loading}
          />
          <p className="mt-1 text-xs text-gray-500">
            Employees arriving this many minutes after shift start will be marked late.
          </p>
        </div>

        <div>
          <span className="label">Weekend / Off Days</span>
          <div className="flex flex-wrap gap-2 mt-1">
            {DAYS_OF_WEEK.map(({ value, label }) => {
              const isSelected = form.weekendDays.includes(value)
              return (
                <button
                  key={value}
                  type="button"
                  onClick={() => toggleWeekendDay(value)}
                  disabled={loading}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                    isSelected
                      ? 'bg-primary-100 border-primary-300 text-primary-700'
                      : 'bg-white border-gray-300 text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  {label}
                </button>
              )
            })}
          </div>
        </div>

        <div className="flex justify-between pt-4">
          <button
            type="button"
            onClick={() => navigate('/setup/company')}
            className="btn-secondary"
            disabled={loading}
          >
            Back
          </button>
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
                Saving...
              </>
            ) : (
              'Next'
            )}
          </button>
        </div>
      </form>
    </div>
  )
}
