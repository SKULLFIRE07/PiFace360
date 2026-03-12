import React, { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import ConfirmDialog from '../components/ConfirmDialog'
import { SkeletonCard } from '../components/Skeleton'
import EmptyState from '../components/EmptyState'
import { UserX, X, Trash2, Edit2, CheckCircle, Eye } from 'lucide-react'

// --- Rename Modal ---
function RenameModal({ open, onClose, unknown }) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState({
    name: '',
    employee_id: '',
    department: '',
    job_title: '',
    phone: '',
  })
  const [successMsg, setSuccessMsg] = useState(null)

  const mutation = useMutation({
    mutationFn: (data) => api.put(`/unknowns/${unknown.id}/rename`, data),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['unknowns'] })
      queryClient.invalidateQueries({ queryKey: ['employees'] })
      setSuccessMsg(
        res.data?.message ||
          `Successfully renamed. ${res.data?.updated_records || 'All'} past records have been updated.`
      )
    },
  })

  const updateField = useCallback((field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }))
  }, [])

  const handleSubmit = useCallback(
    (e) => {
      e.preventDefault()
      setSuccessMsg(null)
      mutation.mutate(form)
    },
    [form, mutation]
  )

  const handleClose = useCallback(() => {
    setSuccessMsg(null)
    setForm({ name: '', employee_id: '', department: '', job_title: '', phone: '' })
    onClose()
  }, [onClose])

  if (!open || !unknown) return null

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center" role="dialog" aria-modal="true">
      <div className="fixed inset-0 bg-black/50" onClick={handleClose} />
      <div className="relative bg-white w-full sm:max-w-lg sm:rounded-xl rounded-t-2xl max-h-[90vh] overflow-y-auto z-10">
        <div className="sticky top-0 bg-white border-b border-gray-100 px-4 sm:px-6 py-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Identify Unknown Person</h2>
          <button onClick={handleClose} className="p-1 text-gray-400 hover:text-gray-600 rounded-lg">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4 sm:p-6">
          {/* Face Snapshot */}
          {unknown.snapshot_url && (
            <div className="flex justify-center mb-4">
              <img
                src={unknown.snapshot_url}
                alt="Unknown person snapshot"
                className="w-32 h-32 rounded-lg object-cover border border-gray-200"
              />
            </div>
          )}

          {successMsg && (
            <div className="flex items-start gap-2 p-3 rounded-lg bg-green-50 text-green-800 text-sm mb-4">
              <CheckCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>{successMsg}</span>
            </div>
          )}

          {!successMsg ? (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label htmlFor="unk-name" className="label">Real Name *</label>
                <input
                  id="unk-name"
                  type="text"
                  required
                  value={form.name}
                  onChange={(e) => updateField('name', e.target.value)}
                  className="input"
                  placeholder="Full name"
                />
              </div>
              <div>
                <label htmlFor="unk-empid" className="label">Employee ID</label>
                <input
                  id="unk-empid"
                  type="text"
                  value={form.employee_id}
                  onChange={(e) => updateField('employee_id', e.target.value)}
                  className="input"
                  placeholder="e.g. EMP001"
                />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="unk-dept" className="label">Department</label>
                  <input
                    id="unk-dept"
                    type="text"
                    value={form.department}
                    onChange={(e) => updateField('department', e.target.value)}
                    className="input"
                  />
                </div>
                <div>
                  <label htmlFor="unk-title" className="label">Job Title</label>
                  <input
                    id="unk-title"
                    type="text"
                    value={form.job_title}
                    onChange={(e) => updateField('job_title', e.target.value)}
                    className="input"
                  />
                </div>
              </div>
              <div>
                <label htmlFor="unk-phone" className="label">Phone</label>
                <input
                  id="unk-phone"
                  type="tel"
                  value={form.phone}
                  onChange={(e) => updateField('phone', e.target.value)}
                  className="input"
                />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={handleClose} className="btn-secondary">
                  Cancel
                </button>
                <button type="submit" disabled={mutation.isPending} className="btn-primary">
                  {mutation.isPending ? (
                    <>
                      <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                      Saving...
                    </>
                  ) : (
                    'Save'
                  )}
                </button>
              </div>
            </form>
          ) : (
            <div className="flex justify-end pt-2">
              <button onClick={handleClose} className="btn-primary">
                Done
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// --- Main Page ---
export default function Unknowns() {
  const queryClient = useQueryClient()
  const [renameTarget, setRenameTarget] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['unknowns'],
    queryFn: () => api.get('/unknowns').then((r) => r.data),
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => api.delete(`/unknowns/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['unknowns'] })
      setDeleteTarget(null)
    },
  })

  const unknowns = data?.unknowns || data || []

  function formatDate(d) {
    if (!d) return '--'
    try {
      return new Date(d).toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    } catch {
      return d
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Unknown Persons</h1>
        <p className="text-sm text-gray-500 mt-1">
          Unidentified visitors detected by the system
        </p>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : error ? (
        <div className="card text-center text-red-600 text-sm py-8">
          Failed to load unknown persons. Please try again.
        </div>
      ) : unknowns.length === 0 ? (
        <EmptyState
          icon={Eye}
          title="No unknown visitors detected yet"
          description="When the system detects an unrecognized person, they will appear here."
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {unknowns.map((u) => (
            <div key={u.id} className="card">
              <div className="flex items-start gap-3">
                {u.snapshot_url ? (
                  <img
                    src={u.snapshot_url}
                    alt={u.label || 'Unknown person'}
                    className="w-16 h-16 rounded-lg object-cover flex-shrink-0 bg-gray-100"
                  />
                ) : (
                  <div className="w-16 h-16 rounded-lg bg-gray-100 flex items-center justify-center flex-shrink-0">
                    <UserX className="w-8 h-8 text-gray-300" />
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-gray-900 truncate">
                    {u.label || u.name || `Unknown ${u.id}`}
                  </p>
                  <div className="mt-1 space-y-0.5 text-xs text-gray-500">
                    <p>Visits: {u.visit_count ?? u.count ?? '--'}</p>
                    <p>First seen: {formatDate(u.first_seen)}</p>
                    <p>Last seen: {formatDate(u.last_seen)}</p>
                  </div>
                </div>
              </div>
              <div className="flex gap-2 mt-3 pt-3 border-t border-gray-100">
                <button
                  onClick={() => setRenameTarget(u)}
                  className="flex-1 btn-primary text-xs py-1.5"
                >
                  <Edit2 className="w-3.5 h-3.5 mr-1" />
                  Rename
                </button>
                <button
                  onClick={() => setDeleteTarget(u)}
                  className="btn-secondary text-xs py-1.5 text-red-600 hover:text-red-700 hover:bg-red-50"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <RenameModal
        open={!!renameTarget}
        onClose={() => setRenameTarget(null)}
        unknown={renameTarget}
      />

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => deleteMutation.mutate(deleteTarget.id)}
        title="Delete Unknown Person"
        message="Are you sure you want to delete this record? This will remove all associated snapshots and visit data."
        confirmText="Delete"
        destructive
        loading={deleteMutation.isPending}
      />
    </div>
  )
}
