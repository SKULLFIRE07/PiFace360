import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Building2, Loader2 } from 'lucide-react'
import { api } from '../../api/client'

export default function CompanyStep() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    companyName: '',
    adminUsername: '',
    adminPassword: '',
    confirmPassword: '',
  })
  const [errors, setErrors] = useState({})
  const [loading, setLoading] = useState(false)
  const [apiError, setApiError] = useState('')

  function validate() {
    const errs = {}
    if (!form.companyName.trim()) errs.companyName = 'Company name is required.'
    if (!form.adminUsername.trim()) errs.adminUsername = 'Username is required.'
    if (!form.adminPassword) errs.adminPassword = 'Password is required.'
    else if (form.adminPassword.length < 8)
      errs.adminPassword = 'Password must be at least 8 characters.'
    if (form.adminPassword !== form.confirmPassword)
      errs.confirmPassword = 'Passwords do not match.'
    return errs
  }

  function handleChange(field) {
    return (e) => {
      setForm((prev) => ({ ...prev, [field]: e.target.value }))
      setErrors((prev) => ({ ...prev, [field]: undefined }))
    }
  }

  async function handleNext(e) {
    e.preventDefault()
    const errs = validate()
    if (Object.keys(errs).length > 0) {
      setErrors(errs)
      return
    }

    setLoading(true)
    setApiError('')
    try {
      await api.post('/setup/company', {
        company_name: form.companyName.trim(),
        admin_username: form.adminUsername.trim(),
        admin_password: form.adminPassword,
      })
      navigate('/setup/hours')
    } catch (err) {
      setApiError(err.response?.data?.detail || 'Failed to save company settings.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 bg-primary-100 rounded-lg flex items-center justify-center">
          <Building2 className="w-5 h-5 text-primary-600" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Company & Admin</h2>
          <p className="text-sm text-gray-500">Set up your organization and admin account</p>
        </div>
      </div>

      {apiError && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {apiError}
        </div>
      )}

      <form onSubmit={handleNext} className="space-y-4">
        <div>
          <label htmlFor="companyName" className="label">
            Company Name
          </label>
          <input
            id="companyName"
            type="text"
            value={form.companyName}
            onChange={handleChange('companyName')}
            className={`input ${errors.companyName ? 'border-red-500' : ''}`}
            placeholder="e.g. Acme Corporation"
            disabled={loading}
          />
          {errors.companyName && (
            <p className="mt-1 text-sm text-red-600">{errors.companyName}</p>
          )}
        </div>

        <div>
          <label htmlFor="adminUsername" className="label">
            Admin Username
          </label>
          <input
            id="adminUsername"
            type="text"
            value={form.adminUsername}
            onChange={handleChange('adminUsername')}
            className={`input ${errors.adminUsername ? 'border-red-500' : ''}`}
            placeholder="admin"
            autoComplete="username"
            disabled={loading}
          />
          {errors.adminUsername && (
            <p className="mt-1 text-sm text-red-600">{errors.adminUsername}</p>
          )}
        </div>

        <div>
          <label htmlFor="adminPassword" className="label">
            Admin Password
          </label>
          <input
            id="adminPassword"
            type="password"
            value={form.adminPassword}
            onChange={handleChange('adminPassword')}
            className={`input ${errors.adminPassword ? 'border-red-500' : ''}`}
            placeholder="Minimum 8 characters"
            autoComplete="new-password"
            disabled={loading}
          />
          {errors.adminPassword && (
            <p className="mt-1 text-sm text-red-600">{errors.adminPassword}</p>
          )}
        </div>

        <div>
          <label htmlFor="confirmPassword" className="label">
            Confirm Password
          </label>
          <input
            id="confirmPassword"
            type="password"
            value={form.confirmPassword}
            onChange={handleChange('confirmPassword')}
            className={`input ${errors.confirmPassword ? 'border-red-500' : ''}`}
            placeholder="Re-enter password"
            autoComplete="new-password"
            disabled={loading}
          />
          {errors.confirmPassword && (
            <p className="mt-1 text-sm text-red-600">{errors.confirmPassword}</p>
          )}
        </div>

        <div className="flex justify-end pt-4">
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
