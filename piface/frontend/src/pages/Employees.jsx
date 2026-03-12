import React, { useState, useMemo, useCallback, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import StatusBadge from '../components/StatusBadge'
import ConfirmDialog from '../components/ConfirmDialog'
import { SkeletonCard } from '../components/Skeleton'
import EmptyState from '../components/EmptyState'
import {
  Plus,
  Search,
  Filter,
  X,
  Upload,
  Edit2,
  Trash2,
  User,
  AlertCircle,
  CheckCircle,
  ChevronDown,
  Camera,
} from 'lucide-react'

// --- Initials Avatar ---
function InitialsAvatar({ name, photoUrl, className = '' }) {
  if (photoUrl) {
    return (
      <img
        src={photoUrl}
        alt={name}
        className={`rounded-full object-cover ${className}`}
      />
    )
  }
  const initials = (name || '?')
    .split(' ')
    .map((w) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)

  return (
    <div
      className={`flex items-center justify-center rounded-full bg-primary-100 text-primary-700 font-bold ${className}`}
      aria-hidden="true"
    >
      {initials}
    </div>
  )
}

// --- Employee Form Modal ---
function EmployeeFormModal({ open, onClose, employee, onSuccess }) {
  const queryClient = useQueryClient()
  const isEdit = !!employee
  const fileInputRef = useRef(null)

  const [form, setForm] = useState({
    name: employee?.name || '',
    employee_id: employee?.employee_id || '',
    department: employee?.department || '',
    job_title: employee?.job_title || '',
    phone: employee?.phone || '',
  })
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(employee?.photo_url || null)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [qualityMsg, setQualityMsg] = useState(null)
  const [showWebcam, setShowWebcam] = useState(false)
  const videoRef = useRef(null)
  const streamRef = useRef(null)

  const mutation = useMutation({
    mutationFn: async (formData) => {
      const config = {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e) => {
          const pct = Math.round((e.loaded * 100) / (e.total || 1))
          setUploadProgress(pct)
        },
      }
      if (isEdit) {
        return api.put(`/employees/${employee.id}`, formData, config)
      }
      return api.post('/employees', formData, config)
    },
    onSuccess: (res) => {
      if (res.data?.quality_warning) {
        setQualityMsg(res.data.quality_warning)
      }
      queryClient.invalidateQueries({ queryKey: ['employees'] })
      onSuccess?.()
      onClose()
    },
    onError: (err) => {
      const msg = err.response?.data?.detail || err.response?.data?.message
      if (msg) {
        setQualityMsg(msg)
      }
    },
  })

  const handleFileChange = useCallback((e) => {
    const f = e.target.files?.[0]
    if (f) {
      setFile(f)
      setQualityMsg(null)
      const reader = new FileReader()
      reader.onload = (ev) => setPreview(ev.target.result)
      reader.readAsDataURL(f)
    }
  }, [])

  const openWebcam = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: 640, height: 480 } })
      streamRef.current = stream
      setShowWebcam(true)
      setTimeout(() => {
        if (videoRef.current) {
          videoRef.current.srcObject = stream
          videoRef.current.play()
        }
      }, 100)
    } catch {
      setQualityMsg('Could not access webcam. Please allow camera permission.')
    }
  }, [])

  const captureWebcam = useCallback(() => {
    if (!videoRef.current) return
    const canvas = document.createElement('canvas')
    canvas.width = videoRef.current.videoWidth || 640
    canvas.height = videoRef.current.videoHeight || 480
    const ctx = canvas.getContext('2d')
    ctx.drawImage(videoRef.current, 0, 0)
    canvas.toBlob((blob) => {
      if (blob) {
        const capturedFile = new File([blob], 'webcam-capture.jpg', { type: 'image/jpeg' })
        setFile(capturedFile)
        setPreview(canvas.toDataURL('image/jpeg'))
        setQualityMsg(null)
      }
      closeWebcam()
    }, 'image/jpeg', 0.9)
  }, [])

  const closeWebcam = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
    setShowWebcam(false)
  }, [])

  const handleSubmit = useCallback(
    (e) => {
      e.preventDefault()
      const fd = new FormData()
      Object.entries(form).forEach(([k, v]) => {
        if (v) fd.append(k, v)
      })
      if (file) fd.append('photo', file)
      setUploadProgress(0)
      mutation.mutate(fd)
    },
    [form, file, mutation]
  )

  const updateField = useCallback((field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }))
  }, [])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center" role="dialog" aria-modal="true">
      <div className="fixed inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-white w-full sm:max-w-lg sm:rounded-xl rounded-t-2xl max-h-[90vh] overflow-y-auto z-10">
        <div className="sticky top-0 bg-white border-b border-gray-100 px-4 sm:px-6 py-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">
            {isEdit ? 'Edit Employee' : 'Add Employee'}
          </h2>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-gray-600 rounded-lg">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 sm:p-6 space-y-4">
          {/* Photo Upload / Webcam Capture */}
          <div className="flex flex-col items-center gap-3">
            {showWebcam ? (
              <div className="w-full space-y-3">
                <div className="relative rounded-lg overflow-hidden bg-black aspect-video max-w-xs mx-auto">
                  <video ref={videoRef} autoPlay playsInline muted className="w-full h-full object-cover" />
                </div>
                <div className="flex justify-center gap-3">
                  <button type="button" onClick={captureWebcam} className="btn-primary text-sm">
                    <Camera className="w-4 h-4 mr-1" /> Capture
                  </button>
                  <button type="button" onClick={closeWebcam} className="btn-secondary text-sm">
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div
                  onClick={() => fileInputRef.current?.click()}
                  className="w-24 h-24 rounded-full bg-gray-100 flex items-center justify-center cursor-pointer hover:bg-gray-200 transition-colors overflow-hidden border-2 border-dashed border-gray-300"
                >
                  {preview ? (
                    <img src={preview} alt="Preview" className="w-full h-full object-cover" />
                  ) : (
                    <Upload className="w-8 h-8 text-gray-400" />
                  )}
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*,video/*"
                  onChange={handleFileChange}
                  className="hidden"
                />
                <div className="flex gap-4">
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="text-sm text-primary-600 hover:text-primary-700 font-medium"
                  >
                    <Upload className="w-3.5 h-3.5 inline mr-1" />
                    {preview ? 'Change Photo' : 'Upload Photo'}
                  </button>
                  <button
                    type="button"
                    onClick={openWebcam}
                    className="text-sm text-green-600 hover:text-green-700 font-medium"
                  >
                    <Camera className="w-3.5 h-3.5 inline mr-1" />
                    Use Webcam
                  </button>
                </div>
              </>
            )}
          </div>

          {/* Upload Progress */}
          {mutation.isPending && uploadProgress > 0 && (
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-primary-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          )}

          {/* Quality Feedback */}
          {qualityMsg && (
            <div className="flex items-start gap-2 p-3 rounded-lg bg-amber-50 text-amber-800 text-sm">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>{qualityMsg}</span>
            </div>
          )}

          {/* Form Fields */}
          <div>
            <label htmlFor="emp-name" className="label">Name *</label>
            <input
              id="emp-name"
              type="text"
              required
              value={form.name}
              onChange={(e) => updateField('name', e.target.value)}
              className="input"
              placeholder="Full name"
            />
          </div>

          <div>
            <label htmlFor="emp-id" className="label">Employee ID *</label>
            <input
              id="emp-id"
              type="text"
              required
              value={form.employee_id}
              onChange={(e) => updateField('employee_id', e.target.value)}
              className="input"
              placeholder="e.g. EMP001"
            />
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label htmlFor="emp-dept" className="label">Department</label>
              <input
                id="emp-dept"
                type="text"
                value={form.department}
                onChange={(e) => updateField('department', e.target.value)}
                className="input"
                placeholder="e.g. Engineering"
              />
            </div>
            <div>
              <label htmlFor="emp-title" className="label">Job Title</label>
              <input
                id="emp-title"
                type="text"
                value={form.job_title}
                onChange={(e) => updateField('job_title', e.target.value)}
                className="input"
                placeholder="e.g. Software Engineer"
              />
            </div>
          </div>

          <div>
            <label htmlFor="emp-phone" className="label">Phone</label>
            <input
              id="emp-phone"
              type="tel"
              value={form.phone}
              onChange={(e) => updateField('phone', e.target.value)}
              className="input"
              placeholder="Phone number"
            />
          </div>

          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="btn-secondary">
              Cancel
            </button>
            <button type="submit" disabled={mutation.isPending} className="btn-primary">
              {mutation.isPending ? (
                <>
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                  {isEdit ? 'Saving...' : 'Adding...'}
                </>
              ) : isEdit ? (
                'Save Changes'
              ) : (
                'Add Employee'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// --- Detail Modal ---
function EmployeeDetailModal({ employee, open, onClose }) {
  const { data: history, isLoading } = useQuery({
    queryKey: ['employees', employee?.id, 'history'],
    queryFn: () => api.get(`/employees/${employee.id}/attendance`).then((r) => r.data),
    enabled: open && !!employee?.id,
  })

  if (!open || !employee) return null

  const records = history?.records || history || []

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center" role="dialog" aria-modal="true">
      <div className="fixed inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-white w-full sm:max-w-lg sm:rounded-xl rounded-t-2xl max-h-[80vh] overflow-y-auto z-10">
        <div className="sticky top-0 bg-white border-b border-gray-100 px-4 sm:px-6 py-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">{employee.name}</h2>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-gray-600 rounded-lg">
            <X className="w-5 h-5" />
          </button>
        </div>
        <div className="p-4 sm:p-6">
          <div className="flex items-center gap-4 mb-4">
            <InitialsAvatar name={employee.name} photoUrl={employee.photo_url} className="w-16 h-16 text-xl" />
            <div>
              <p className="text-sm text-gray-500">ID: {employee.employee_id}</p>
              <p className="text-sm text-gray-500">{employee.department}</p>
              <p className="text-sm text-gray-500">{employee.job_title}</p>
            </div>
          </div>
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Attendance History</h3>
          {isLoading ? (
            <div className="animate-pulse space-y-2">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="h-8 bg-gray-100 rounded" />
              ))}
            </div>
          ) : records.length === 0 ? (
            <p className="text-sm text-gray-500 text-center py-4">No attendance records found.</p>
          ) : (
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {records.map((r, i) => (
                <div key={r.id || i} className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded-lg text-sm">
                  <span className="text-gray-700">{r.date || new Date(r.timestamp).toLocaleDateString()}</span>
                  <StatusBadge status={r.status === 'present' || r.event_type === 'IN' ? 'in' : r.status === 'absent' ? 'not_arrived' : 'out'} />
                  <span className="text-gray-500">{r.hours ? `${r.hours}h` : r.time || '--'}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// --- Main Page ---
export default function Employees() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [deptFilter, setDeptFilter] = useState('')
  const [showAdd, setShowAdd] = useState(false)
  const [editEmployee, setEditEmployee] = useState(null)
  const [detailEmployee, setDetailEmployee] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['employees'],
    queryFn: () => api.get('/employees').then((r) => r.data),
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => api.delete(`/employees/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['employees'] })
      setDeleteTarget(null)
    },
  })

  const employees = data?.employees || data || []

  const departments = useMemo(() => {
    const depts = new Set(employees.map((e) => e.department).filter(Boolean))
    return Array.from(depts).sort()
  }, [employees])

  const filtered = useMemo(() => {
    let list = employees
    if (search) {
      const q = search.toLowerCase()
      list = list.filter(
        (e) =>
          e.name?.toLowerCase().includes(q) ||
          e.employee_id?.toLowerCase().includes(q)
      )
    }
    if (deptFilter) {
      list = list.filter((e) => e.department === deptFilter)
    }
    return list
  }, [employees, search, deptFilter])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Employees</h1>
          <p className="text-sm text-gray-500 mt-1">
            {employees.length} registered employee{employees.length !== 1 ? 's' : ''}
          </p>
        </div>
        <button
          onClick={() => setShowAdd(true)}
          className="btn-primary hidden sm:inline-flex"
        >
          <Plus className="w-4 h-4 mr-2" />
          Add Employee
        </button>
      </div>

      {/* Search and Filter */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by name or ID..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input pl-9"
          />
        </div>
        <div className="relative">
          <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <select
            value={deptFilter}
            onChange={(e) => setDeptFilter(e.target.value)}
            className="input pl-9 pr-8 appearance-none"
          >
            <option value="">All Departments</option>
            {departments.map((d) => (
              <option key={d} value={d}>{d}</option>
            ))}
          </select>
          <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
        </div>
      </div>

      {/* Employee Grid */}
      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : error ? (
        <div className="card text-center text-red-600 text-sm py-8">
          Failed to load employees. Please try again.
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={User}
          title={search || deptFilter ? 'No matches found' : 'No employees yet'}
          description={
            search || deptFilter
              ? 'Try adjusting your search or filter.'
              : 'Add your first employee to get started.'
          }
          actionLabel={!search && !deptFilter ? 'Add Employee' : undefined}
          onAction={!search && !deptFilter ? () => setShowAdd(true) : undefined}
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((emp) => (
            <div
              key={emp.id || emp.employee_id}
              className="card hover:shadow-md transition-shadow cursor-pointer group"
              onClick={() => setDetailEmployee(emp)}
            >
              <div className="flex items-start gap-3">
                <InitialsAvatar
                  name={emp.name}
                  photoUrl={emp.photo_url}
                  className="w-12 h-12 flex-shrink-0 text-base"
                />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-gray-900 truncate">{emp.name}</p>
                  <p className="text-xs text-gray-500">{emp.employee_id}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{emp.department || '--'}</p>
                  <p className="text-xs text-gray-400">{emp.job_title || '--'}</p>
                </div>
                <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      setEditEmployee(emp)
                    }}
                    className="p-1.5 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg"
                    aria-label={`Edit ${emp.name}`}
                  >
                    <Edit2 className="w-4 h-4" />
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      setDeleteTarget(emp)
                    }}
                    className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg"
                    aria-label={`Delete ${emp.name}`}
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* FAB for mobile */}
      <button
        onClick={() => setShowAdd(true)}
        className="sm:hidden fixed bottom-6 right-6 z-40 w-14 h-14 bg-primary-600 text-white rounded-full shadow-lg hover:bg-primary-700 flex items-center justify-center transition-colors"
        aria-label="Add Employee"
      >
        <Plus className="w-6 h-6" />
      </button>

      {/* Modals */}
      <EmployeeFormModal
        open={showAdd}
        onClose={() => setShowAdd(false)}
      />

      {editEmployee && (
        <EmployeeFormModal
          open={true}
          onClose={() => setEditEmployee(null)}
          employee={editEmployee}
        />
      )}

      <EmployeeDetailModal
        open={!!detailEmployee}
        employee={detailEmployee}
        onClose={() => setDetailEmployee(null)}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => deleteMutation.mutate(deleteTarget.id)}
        title="Delete Employee"
        message={`Are you sure you want to delete ${deleteTarget?.name}? This action cannot be undone.`}
        confirmText="Delete"
        destructive
        loading={deleteMutation.isPending}
      />
    </div>
  )
}
