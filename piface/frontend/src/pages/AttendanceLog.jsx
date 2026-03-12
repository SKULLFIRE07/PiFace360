import React, { useState, useMemo, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import StatusBadge from '../components/StatusBadge'
import ConfirmDialog from '../components/ConfirmDialog'
import { SkeletonTable, SkeletonCard } from '../components/Skeleton'
import EmptyState from '../components/EmptyState'
import {
  Filter,
  Download,
  Plus,
  Edit2,
  Trash2,
  X,
  ChevronDown,
  ChevronUp,
  ChevronLeft,
  ChevronRight,
  Image,
  FileText,
  ToggleLeft,
  ToggleRight,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
} from 'lucide-react'

function formatDateTime(d) {
  if (!d) return '--'
  try {
    return new Date(d).toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return d
  }
}

// --- Add/Edit Event Modal ---
function EventFormModal({ open, onClose, event, employees }) {
  const queryClient = useQueryClient()
  const isEdit = !!event

  const [form, setForm] = useState({
    person_id: event?.person_id || '',
    event_type: event?.event_type || 'IN',
    timestamp: event?.timestamp
      ? new Date(event.timestamp).toISOString().slice(0, 16)
      : new Date().toISOString().slice(0, 16),
  })

  const mutation = useMutation({
    mutationFn: (data) => {
      if (isEdit) return api.put(`/attendance/${event.id}`, data)
      return api.post('/attendance', data)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['attendance'] })
      onClose()
    },
  })

  const updateField = useCallback((field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }))
  }, [])

  const handleSubmit = useCallback(
    (e) => {
      e.preventDefault()
      mutation.mutate(form)
    },
    [form, mutation]
  )

  if (!open) return null

  const empList = employees || []

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center" role="dialog" aria-modal="true">
      <div className="fixed inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-white w-full sm:max-w-md sm:rounded-xl rounded-t-2xl z-10">
        <div className="px-4 sm:px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">
            {isEdit ? 'Edit Event' : 'Add Manual Event'}
          </h2>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-gray-600 rounded-lg">
            <X className="w-5 h-5" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-4 sm:p-6 space-y-4">
          <div>
            <label htmlFor="evt-person" className="label">Person *</label>
            <select
              id="evt-person"
              required
              value={form.person_id}
              onChange={(e) => updateField('person_id', e.target.value)}
              className="input"
            >
              <option value="">Select person...</option>
              {empList.map((emp) => (
                <option key={emp.id} value={emp.id}>
                  {emp.name} ({emp.employee_id})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="evt-type" className="label">Event Type *</label>
            <select
              id="evt-type"
              value={form.event_type}
              onChange={(e) => updateField('event_type', e.target.value)}
              className="input"
            >
              <option value="IN">IN</option>
              <option value="OUT">OUT</option>
            </select>
          </div>
          <div>
            <label htmlFor="evt-time" className="label">Date & Time *</label>
            <input
              id="evt-time"
              type="datetime-local"
              required
              value={form.timestamp}
              onChange={(e) => updateField('timestamp', e.target.value)}
              className="input"
            />
          </div>
          {mutation.isError && (
            <p className="text-sm text-red-600">
              {mutation.error?.response?.data?.detail || 'Failed to save event.'}
            </p>
          )}
          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className="btn-secondary">Cancel</button>
            <button type="submit" disabled={mutation.isPending} className="btn-primary">
              {mutation.isPending ? (
                <>
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                  Saving...
                </>
              ) : isEdit ? (
                'Save Changes'
              ) : (
                'Add Event'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// --- Expandable Row ---
function ExpandableRow({ record, onEdit, onDelete }) {
  const [expanded, setExpanded] = useState(false)
  const isIn = record.event_type === 'IN' || record.event_type === 'in'

  return (
    <>
      <tr
        className="border-b border-gray-100 last:border-0 hover:bg-gray-50 transition-colors cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <td className="py-3 px-4 text-sm text-gray-700">{formatDateTime(record.timestamp)}</td>
        <td className="py-3 px-4 text-sm font-medium text-gray-900">{record.person_name || record.name || '--'}</td>
        <td className="py-3 px-4 text-sm text-gray-500">{record.department || '--'}</td>
        <td className="py-3 px-4">
          <StatusBadge status={isIn ? 'in' : 'out'} />
        </td>
        <td className="py-3 px-4 text-sm text-gray-500">
          {record.confidence != null ? `${Math.round(record.confidence * 100)}%` : '--'}
        </td>
        <td className="py-3 px-4">
          {record.manual && (
            <span className="inline-flex items-center gap-1 text-xs text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full font-medium">
              <Edit2 className="w-3 h-3" />
              Manual
            </span>
          )}
        </td>
        <td className="py-3 px-4">
          <div className="flex items-center gap-1">
            <button
              onClick={(e) => { e.stopPropagation(); onEdit(record) }}
              className="p-1.5 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg"
              aria-label="Edit event"
            >
              <Edit2 className="w-3.5 h-3.5" />
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(record) }}
              className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg"
              aria-label="Delete event"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
            {expanded ? (
              <ChevronUp className="w-4 h-4 text-gray-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-gray-400" />
            )}
          </div>
        </td>
      </tr>
      {expanded && (
        <tr className="bg-gray-50">
          <td colSpan={7} className="px-4 py-3">
            <div className="flex items-center gap-4">
              {record.snapshot_url ? (
                <img
                  src={record.snapshot_url}
                  alt="Face snapshot"
                  className="w-16 h-16 rounded-lg object-cover border border-gray-200"
                />
              ) : (
                <div className="w-16 h-16 rounded-lg bg-gray-200 flex items-center justify-center">
                  <Image className="w-6 h-6 text-gray-400" />
                </div>
              )}
              <div className="text-sm text-gray-600 space-y-1">
                <p>Person ID: {record.person_id || '--'}</p>
                <p>Source: {record.manual ? 'Manual correction' : 'Face recognition'}</p>
                {record.confidence != null && (
                  <p>Confidence: {(record.confidence * 100).toFixed(1)}%</p>
                )}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

// --- Mobile Card ---
function MobileEventCard({ record, onEdit, onDelete }) {
  const [expanded, setExpanded] = useState(false)
  const isIn = record.event_type === 'IN' || record.event_type === 'in'

  return (
    <div className="card" onClick={() => setExpanded(!expanded)}>
      <div className="flex items-center justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium text-gray-900 truncate">{record.person_name || record.name || '--'}</p>
            <StatusBadge status={isIn ? 'in' : 'out'} />
            {record.manual && (
              <span className="text-xs text-amber-600 font-medium">Manual</span>
            )}
          </div>
          <p className="text-xs text-gray-500 mt-0.5">
            {record.department || '--'} -- {formatDateTime(record.timestamp)}
          </p>
          {record.confidence != null && (
            <p className="text-xs text-gray-400 mt-0.5">
              Confidence: {Math.round(record.confidence * 100)}%
            </p>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={(e) => { e.stopPropagation(); onEdit(record) }}
            className="p-1.5 text-gray-400 hover:text-primary-600 rounded-lg"
            aria-label="Edit"
          >
            <Edit2 className="w-4 h-4" />
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); onDelete(record) }}
            className="p-1.5 text-gray-400 hover:text-red-600 rounded-lg"
            aria-label="Delete"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
      {expanded && record.snapshot_url && (
        <div className="mt-3 pt-3 border-t border-gray-100">
          <img
            src={record.snapshot_url}
            alt="Face snapshot"
            className="w-16 h-16 rounded-lg object-cover border border-gray-200"
          />
        </div>
      )}
    </div>
  )
}

// --- Main Page ---
export default function AttendanceLog() {
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [perPage, setPerPage] = useState(20)
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [personFilter, setPersonFilter] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [manualOnly, setManualOnly] = useState(false)
  const [showAddModal, setShowAddModal] = useState(false)
  const [editEvent, setEditEvent] = useState(null)
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [sortField, setSortField] = useState('timestamp')
  const [sortOrder, setSortOrder] = useState('desc')

  const queryParams = useMemo(() => {
    const params = { page, per_page: perPage }
    if (dateFrom) params.date_from = dateFrom
    if (dateTo) params.date_to = dateTo
    if (personFilter) params.person_id = personFilter
    if (typeFilter) params.event_type = typeFilter
    if (manualOnly) params.manual_only = true
    params.sort_by = sortField
    params.sort_order = sortOrder
    return params
  }, [page, perPage, dateFrom, dateTo, personFilter, typeFilter, manualOnly, sortField, sortOrder])

  const { data, isLoading, error } = useQuery({
    queryKey: ['attendance', queryParams],
    queryFn: () => api.get('/attendance', { params: queryParams }).then((r) => r.data),
  })

  const { data: employeeData } = useQuery({
    queryKey: ['employees'],
    queryFn: () => api.get('/employees').then((r) => r.data),
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => api.delete(`/attendance/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['attendance'] })
      setDeleteTarget(null)
    },
  })

  const records = data?.records || data?.events || (Array.isArray(data) ? data : [])
  const totalPages = data?.total_pages || Math.ceil((data?.total || records.length) / perPage) || 1
  const employees = employeeData?.employees || (Array.isArray(employeeData) ? employeeData : [])

  const handleSort = useCallback((field) => {
    if (sortField === field) {
      setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortOrder('asc')
    }
    setPage(1)
  }, [sortField])

  const SortIcon = useCallback(({ field }) => {
    if (sortField !== field) return <ArrowUpDown className="w-3.5 h-3.5 text-gray-300" />
    return sortOrder === 'asc'
      ? <ArrowUp className="w-3.5 h-3.5 text-primary-600" />
      : <ArrowDown className="w-3.5 h-3.5 text-primary-600" />
  }, [sortField, sortOrder])

  const handleExportCSV = useCallback(() => {
    const params = new URLSearchParams()
    if (dateFrom) params.set('date_from', dateFrom)
    if (dateTo) params.set('date_to', dateTo)
    if (personFilter) params.set('person_id', personFilter)
    if (typeFilter) params.set('event_type', typeFilter)
    if (manualOnly) params.set('manual_only', 'true')
    window.open(`/api/attendance/export?${params.toString()}`, '_blank')
  }, [dateFrom, dateTo, personFilter, typeFilter, manualOnly])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Attendance Log</h1>
          <p className="text-sm text-gray-500 mt-1">Complete event history</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setShowAddModal(true)} className="btn-primary text-sm">
            <Plus className="w-4 h-4 mr-1" />
            Add Event
          </button>
          <button onClick={handleExportCSV} className="btn-secondary text-sm">
            <Download className="w-4 h-4 mr-1" />
            Download as CSV
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div className="card">
        <div className="flex items-center gap-2 mb-3">
          <Filter className="w-4 h-4 text-gray-500" />
          <h3 className="text-sm font-semibold text-gray-700">Filters</h3>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          <div>
            <label htmlFor="filter-from" className="label">From</label>
            <input
              id="filter-from"
              type="date"
              value={dateFrom}
              onChange={(e) => { setDateFrom(e.target.value); setPage(1) }}
              className="input"
            />
          </div>
          <div>
            <label htmlFor="filter-to" className="label">To</label>
            <input
              id="filter-to"
              type="date"
              value={dateTo}
              onChange={(e) => { setDateTo(e.target.value); setPage(1) }}
              className="input"
            />
          </div>
          <div>
            <label htmlFor="filter-person" className="label">Person</label>
            <select
              id="filter-person"
              value={personFilter}
              onChange={(e) => { setPersonFilter(e.target.value); setPage(1) }}
              className="input"
            >
              <option value="">All</option>
              {employees.map((emp) => (
                <option key={emp.id} value={emp.id}>
                  {emp.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="filter-type" className="label">Event Type</label>
            <select
              id="filter-type"
              value={typeFilter}
              onChange={(e) => { setTypeFilter(e.target.value); setPage(1) }}
              className="input"
            >
              <option value="">All</option>
              <option value="IN">IN</option>
              <option value="OUT">OUT</option>
            </select>
          </div>
          <div>
            <label className="label">Manual Only</label>
            <button
              onClick={() => { setManualOnly(!manualOnly); setPage(1) }}
              className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-sm w-full transition-colors ${
                manualOnly
                  ? 'bg-primary-50 border-primary-300 text-primary-700'
                  : 'bg-white border-gray-300 text-gray-600'
              }`}
            >
              {manualOnly ? (
                <ToggleRight className="w-5 h-5" />
              ) : (
                <ToggleLeft className="w-5 h-5" />
              )}
              {manualOnly ? 'On' : 'Off'}
            </button>
          </div>
        </div>
        <div className="flex items-center gap-3 mt-3 pt-3 border-t border-gray-100">
          <ArrowUpDown className="w-4 h-4 text-gray-500 shrink-0" />
          <span className="text-sm font-semibold text-gray-700 shrink-0">Sort</span>
          <div>
            <select
              id="sort-field"
              value={sortField}
              onChange={(e) => { setSortField(e.target.value); setPage(1) }}
              className="input"
              aria-label="Sort by"
            >
              <option value="timestamp">Time</option>
              <option value="person_name">Person Name</option>
              <option value="department">Department</option>
              <option value="event_type">Event Type</option>
            </select>
          </div>
          <button
            onClick={() => { setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc')); setPage(1) }}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-lg border text-sm transition-colors ${
              sortOrder === 'asc'
                ? 'bg-primary-50 border-primary-300 text-primary-700'
                : 'bg-white border-gray-300 text-gray-600'
            }`}
            aria-label={`Sort order: ${sortOrder === 'asc' ? 'Ascending' : 'Descending'}`}
          >
            {sortOrder === 'asc' ? (
              <><ArrowUp className="w-4 h-4" /> Asc</>
            ) : (
              <><ArrowDown className="w-4 h-4" /> Desc</>
            )}
          </button>
        </div>
      </div>

      {/* Records */}
      {isLoading ? (
        <>
          <div className="hidden sm:block card p-0">
            <div className="p-4"><SkeletonTable rows={5} cols={6} /></div>
          </div>
          <div className="sm:hidden space-y-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        </>
      ) : error ? (
        <div className="card text-center text-red-600 text-sm py-8">
          Failed to load attendance records. Please try again.
        </div>
      ) : records.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="No records found"
          description="Try adjusting your filters or add a manual event."
        />
      ) : (
        <>
          {/* Desktop Table */}
          <div className="hidden sm:block card p-0">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider border-b border-gray-100">
                    <th className="py-3 px-4">
                      <button onClick={() => handleSort('timestamp')} className="inline-flex items-center gap-1 hover:text-gray-700 transition-colors">
                        Time <SortIcon field="timestamp" />
                      </button>
                    </th>
                    <th className="py-3 px-4">
                      <button onClick={() => handleSort('person_name')} className="inline-flex items-center gap-1 hover:text-gray-700 transition-colors">
                        Person <SortIcon field="person_name" />
                      </button>
                    </th>
                    <th className="py-3 px-4">
                      <button onClick={() => handleSort('department')} className="inline-flex items-center gap-1 hover:text-gray-700 transition-colors">
                        Department <SortIcon field="department" />
                      </button>
                    </th>
                    <th className="py-3 px-4">
                      <button onClick={() => handleSort('event_type')} className="inline-flex items-center gap-1 hover:text-gray-700 transition-colors">
                        Type <SortIcon field="event_type" />
                      </button>
                    </th>
                    <th className="py-3 px-4">
                      <button onClick={() => handleSort('confidence')} className="inline-flex items-center gap-1 hover:text-gray-700 transition-colors">
                        Confidence <SortIcon field="confidence" />
                      </button>
                    </th>
                    <th className="py-3 px-4">Flag</th>
                    <th className="py-3 px-4">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {records.map((r) => (
                    <ExpandableRow
                      key={r.id}
                      record={r}
                      onEdit={setEditEvent}
                      onDelete={setDeleteTarget}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Mobile Cards */}
          <div className="sm:hidden space-y-3">
            {records.map((r) => (
              <MobileEventCard
                key={r.id}
                record={r}
                onEdit={setEditEvent}
                onDelete={setDeleteTarget}
              />
            ))}
          </div>

          {/* Pagination */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <label htmlFor="per-page" className="text-sm text-gray-600">Per page:</label>
              <select
                id="per-page"
                value={perPage}
                onChange={(e) => { setPerPage(Number(e.target.value)); setPage(1) }}
                className="input w-20"
              >
                <option value={10}>10</option>
                <option value={20}>20</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
                className="btn-secondary p-2"
                aria-label="Previous page"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              {Array.from({ length: Math.min(totalPages, 5) }).map((_, i) => {
                let pageNum
                if (totalPages <= 5) {
                  pageNum = i + 1
                } else if (page <= 3) {
                  pageNum = i + 1
                } else if (page >= totalPages - 2) {
                  pageNum = totalPages - 4 + i
                } else {
                  pageNum = page - 2 + i
                }
                return (
                  <button
                    key={pageNum}
                    onClick={() => setPage(pageNum)}
                    className={`w-9 h-9 rounded-lg text-sm font-medium transition-colors ${
                      page === pageNum
                        ? 'bg-primary-600 text-white'
                        : 'text-gray-600 hover:bg-gray-100'
                    }`}
                  >
                    {pageNum}
                  </button>
                )
              })}
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
                className="btn-secondary p-2"
                aria-label="Next page"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </>
      )}

      {/* Modals */}
      <EventFormModal
        open={showAddModal}
        onClose={() => setShowAddModal(false)}
        employees={employees}
      />

      {editEvent && (
        <EventFormModal
          open={true}
          onClose={() => setEditEvent(null)}
          event={editEvent}
          employees={employees}
        />
      )}

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => deleteMutation.mutate(deleteTarget.id)}
        title="Delete Event"
        message="Are you sure you want to delete this attendance event? This action cannot be undone."
        confirmText="Delete"
        destructive
        loading={deleteMutation.isPending}
      />
    </div>
  )
}
