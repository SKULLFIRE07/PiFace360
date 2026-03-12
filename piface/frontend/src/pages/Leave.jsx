import React, { useState, useMemo, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import ConfirmDialog from '../components/ConfirmDialog'
import { SkeletonTable } from '../components/Skeleton'
import EmptyState from '../components/EmptyState'
import {
  Calendar,
  Plus,
  Trash2,
  X,
  ChevronLeft,
  ChevronRight,
  Search,
  ChevronDown,
  Star,
} from 'lucide-react'

// --- Calendar helpers ---
function getDaysInMonth(year, month) {
  return new Date(year, month + 1, 0).getDate()
}

function getFirstDayOfMonth(year, month) {
  return new Date(year, month, 1).getDay()
}

function dateKey(y, m, d) {
  return `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
}

const dotColors = {
  present: 'bg-green-500',
  absent: 'bg-red-500',
  leave: 'bg-blue-500',
  holiday: 'bg-purple-500',
}

const badgeColors = {
  Vacation: 'bg-blue-100 text-blue-700',
  Sick: 'bg-red-100 text-red-700',
  Personal: 'bg-amber-100 text-amber-700',
  WFH: 'bg-green-100 text-green-700',
}

function getInitials(name) {
  if (!name) return '?'
  return name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
}

// --- Calendar View ---
function CalendarView({ year, month, onChangeMonth, dayStatuses, leaves, holidays }) {
  const [selectedDay, setSelectedDay] = useState(null)

  const daysInMonth = getDaysInMonth(year, month)
  const firstDay = getFirstDayOfMonth(year, month)
  const monthName = new Date(year, month).toLocaleDateString(undefined, {
    month: 'long',
    year: 'numeric',
  })

  const prevMonth = useCallback(() => {
    setSelectedDay(null)
    if (month === 0) onChangeMonth(year - 1, 11)
    else onChangeMonth(year, month - 1)
  }, [year, month, onChangeMonth])

  const nextMonth = useCallback(() => {
    setSelectedDay(null)
    if (month === 11) onChangeMonth(year + 1, 0)
    else onChangeMonth(year, month + 1)
  }, [year, month, onChangeMonth])

  // Build a map of dateKey -> array of leave/holiday entries for the current month
  const dayEntries = useMemo(() => {
    const entries = {}
    leaves.forEach((l) => {
      const start = new Date(l.start_date || l.date)
      const end = new Date(l.end_date || l.date)
      for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
        const key = d.toISOString().split('T')[0]
        if (!entries[key]) entries[key] = []
        entries[key].push({ type: 'leave', data: l })
      }
    })
    holidays.forEach((h) => {
      if (h.date) {
        if (!entries[h.date]) entries[h.date] = []
        entries[h.date].push({ type: 'holiday', data: h })
      }
    })
    return entries
  }, [leaves, holidays])

  // Get entries for the selected day
  const selectedEntries = selectedDay ? dayEntries[selectedDay] || [] : []

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <button onClick={prevMonth} className="btn-secondary p-2" aria-label="Previous month">
          <ChevronLeft className="w-4 h-4" />
        </button>
        <h3 className="text-sm font-semibold text-gray-900">{monthName}</h3>
        <button onClick={nextMonth} className="btn-secondary p-2" aria-label="Next month">
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>

      <div className="grid grid-cols-7 gap-1">
        {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((d) => (
          <div key={d} className="text-center text-xs font-medium text-gray-500 py-1">
            {d}
          </div>
        ))}

        {/* Empty cells for days before month starts */}
        {Array.from({ length: firstDay }).map((_, i) => (
          <div key={`empty-${i}`} className="min-h-[4rem]" />
        ))}

        {/* Day cells */}
        {Array.from({ length: daysInMonth }).map((_, i) => {
          const day = i + 1
          const key = dateKey(year, month, day)
          const status = dayStatuses[key]
          const isToday = key === new Date().toISOString().split('T')[0]
          const isSelected = key === selectedDay
          const entries = dayEntries[key] || []
          const hasEntries = entries.length > 0

          return (
            <div
              key={day}
              role={hasEntries ? 'button' : undefined}
              tabIndex={hasEntries ? 0 : undefined}
              onClick={() => {
                if (hasEntries) setSelectedDay(isSelected ? null : key)
              }}
              onKeyDown={(e) => {
                if (hasEntries && (e.key === 'Enter' || e.key === ' ')) {
                  e.preventDefault()
                  setSelectedDay(isSelected ? null : key)
                }
              }}
              title={
                hasEntries
                  ? entries
                      .map((e) =>
                        e.type === 'holiday'
                          ? `Holiday: ${e.data.name}`
                          : `${e.data.employee_name || 'Employee'} - ${e.data.leave_type || 'Leave'}${e.data.note ? ': ' + e.data.note : ''}`
                      )
                      .join('\n')
                  : undefined
              }
              className={`min-h-[4rem] flex flex-col items-center rounded-lg text-sm relative p-1 transition-colors ${
                isSelected
                  ? 'ring-2 ring-primary-500 bg-primary-50'
                  : isToday
                    ? 'bg-primary-50 font-semibold text-primary-700'
                    : hasEntries
                      ? 'hover:bg-gray-50 cursor-pointer'
                      : 'text-gray-700'
              }`}
            >
              <span className={`${isToday && !isSelected ? 'font-semibold text-primary-700' : ''}`}>
                {day}
              </span>

              {/* Show employee initials + leave type badges */}
              <div className="flex flex-col items-center gap-0.5 mt-0.5 w-full overflow-hidden">
                {entries.slice(0, 2).map((entry, idx) =>
                  entry.type === 'holiday' ? (
                    <span
                      key={`h-${idx}`}
                      className="inline-flex items-center px-1 py-0 text-[9px] font-medium rounded bg-purple-100 text-purple-700 leading-tight truncate max-w-full"
                    >
                      {entry.data.name.length > 8 ? entry.data.name.slice(0, 8) + '..' : entry.data.name}
                    </span>
                  ) : (
                    <span
                      key={`l-${idx}`}
                      className={`inline-flex items-center gap-0.5 px-1 py-0 text-[9px] font-medium rounded leading-tight truncate max-w-full ${badgeColors[entry.data.leave_type] || 'bg-blue-100 text-blue-700'}`}
                    >
                      <span className="font-bold">{getInitials(entry.data.employee_name)}</span>
                      <span className="hidden sm:inline">{entry.data.leave_type ? entry.data.leave_type.slice(0, 3) : ''}</span>
                    </span>
                  )
                )}
                {entries.length > 2 && (
                  <span className="text-[9px] text-gray-400 leading-tight">
                    +{entries.length - 2}
                  </span>
                )}
              </div>

              {/* Fallback dot for calendar API statuses without leave/holiday entries */}
              {status && entries.length === 0 && (
                <span
                  className={`absolute bottom-1 w-1.5 h-1.5 rounded-full ${dotColors[status] || dotColors.present}`}
                  aria-label={status}
                />
              )}
            </div>
          )
        })}
      </div>

      {/* Selected day detail panel */}
      {selectedDay && (
        <div className="mt-4 pt-4 border-t border-gray-200">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-semibold text-gray-800">
              {new Date(selectedDay + 'T00:00:00').toLocaleDateString(undefined, {
                weekday: 'long',
                month: 'long',
                day: 'numeric',
                year: 'numeric',
              })}
            </h4>
            <button
              onClick={() => setSelectedDay(null)}
              className="p-1 text-gray-400 hover:text-gray-600 rounded-lg"
              aria-label="Close details"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {selectedEntries.length === 0 ? (
            <p className="text-sm text-gray-500">No leave or holiday entries for this day.</p>
          ) : (
            <div className="space-y-2">
              {selectedEntries.map((entry, idx) =>
                entry.type === 'holiday' ? (
                  <div
                    key={`detail-h-${idx}`}
                    className="flex items-center gap-3 p-3 bg-purple-50 rounded-lg"
                  >
                    <span className="w-2 h-2 rounded-full bg-purple-500 shrink-0" />
                    <div>
                      <p className="text-sm font-medium text-purple-800">Holiday: {entry.data.name}</p>
                    </div>
                  </div>
                ) : (
                  <div
                    key={`detail-l-${idx}`}
                    className="flex items-start gap-3 p-3 bg-blue-50 rounded-lg"
                  >
                    <span className="w-6 h-6 rounded-full bg-blue-200 text-blue-800 text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
                      {getInitials(entry.data.employee_name)}
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-900">
                        {entry.data.employee_name || 'Unknown Employee'}
                      </p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span
                          className={`inline-flex px-2 py-0.5 text-xs font-medium rounded-full ${badgeColors[entry.data.leave_type] || 'bg-blue-100 text-blue-700'}`}
                        >
                          {entry.data.leave_type || 'Leave'}
                        </span>
                      </div>
                      {entry.data.note && (
                        <p className="text-xs text-gray-600 mt-1">{entry.data.note}</p>
                      )}
                    </div>
                  </div>
                )
              )}
            </div>
          )}
        </div>
      )}

      {/* Legend */}
      <div className="flex flex-wrap gap-4 mt-4 pt-3 border-t border-gray-100">
        {Object.entries(dotColors).map(([label, color]) => (
          <div key={label} className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${color}`} />
            <span className="text-xs text-gray-500 capitalize">{label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// --- Add Leave Form ---
function AddLeaveForm({ employees, onClose }) {
  const queryClient = useQueryClient()

  const [form, setForm] = useState({
    employee_id: '',
    start_date: new Date().toISOString().split('T')[0],
    end_date: new Date().toISOString().split('T')[0],
    leave_type: 'Vacation',
    note: '',
  })

  const [empSearch, setEmpSearch] = useState('')

  const filteredEmps = useMemo(() => {
    if (!empSearch) return employees
    const q = empSearch.toLowerCase()
    return employees.filter((e) => e.name?.toLowerCase().includes(q))
  }, [employees, empSearch])

  const mutation = useMutation({
    mutationFn: (data) => api.post('/leave', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leaves'] })
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

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-700">Add Leave</h3>
        <button onClick={onClose} className="p-1 text-gray-400 hover:text-gray-600 rounded-lg">
          <X className="w-4 h-4" />
        </button>
      </div>

      {mutation.isError && (
        <div className="mb-4 p-3 bg-red-50 rounded-lg text-sm text-red-700">
          {mutation.error?.response?.data?.detail || 'Failed to add leave.'}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="label">Employee *</label>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={empSearch}
              onChange={(e) => setEmpSearch(e.target.value)}
              className="input pl-9 mb-1"
              placeholder="Search employee..."
            />
          </div>
          <select
            required
            value={form.employee_id}
            onChange={(e) => updateField('employee_id', e.target.value)}
            className="input"
            size={Math.min(filteredEmps.length + 1, 5)}
          >
            <option value="">Select employee...</option>
            {filteredEmps.map((emp) => (
              <option key={emp.id} value={emp.id}>
                {emp.name} ({emp.employee_id})
              </option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="label">Start Date *</label>
            <input
              type="date"
              required
              value={form.start_date}
              onChange={(e) => updateField('start_date', e.target.value)}
              className="input"
            />
          </div>
          <div>
            <label className="label">End Date *</label>
            <input
              type="date"
              required
              value={form.end_date}
              onChange={(e) => updateField('end_date', e.target.value)}
              className="input"
            />
          </div>
        </div>

        <div>
          <label className="label">Leave Type *</label>
          <div className="relative">
            <select
              value={form.leave_type}
              onChange={(e) => updateField('leave_type', e.target.value)}
              className="input appearance-none pr-8"
            >
              <option value="Vacation">Vacation</option>
              <option value="Sick">Sick</option>
              <option value="Personal">Personal</option>
              <option value="WFH">Work From Home</option>
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
          </div>
        </div>

        <div>
          <label className="label">Note (optional)</label>
          <textarea
            value={form.note}
            onChange={(e) => updateField('note', e.target.value)}
            className="input"
            rows={2}
            placeholder="Optional note"
          />
        </div>

        <div className="flex justify-end gap-3">
          <button type="button" onClick={onClose} className="btn-secondary">Cancel</button>
          <button type="submit" disabled={mutation.isPending} className="btn-primary">
            {mutation.isPending ? (
              <>
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                Submitting...
              </>
            ) : (
              'Submit Leave'
            )}
          </button>
        </div>
      </form>
    </div>
  )
}

// --- Add Holiday Form ---
function AddHolidayForm({ onClose }) {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [date, setDate] = useState(new Date().toISOString().split('T')[0])

  const mutation = useMutation({
    mutationFn: (data) => api.post('/holidays', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['holidays'] })
      onClose()
    },
  })

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        mutation.mutate({ name, date })
      }}
      className="flex flex-col sm:flex-row gap-3 items-end"
    >
      <div className="flex-1">
        <label className="label">Date</label>
        <input type="date" required value={date} onChange={(e) => setDate(e.target.value)} className="input" />
      </div>
      <div className="flex-1">
        <label className="label">Holiday Name</label>
        <input
          type="text"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="input"
          placeholder="e.g. New Year's Day"
        />
      </div>
      <button type="submit" disabled={mutation.isPending} className="btn-primary whitespace-nowrap">
        {mutation.isPending ? 'Adding...' : 'Add Holiday'}
      </button>
      <button type="button" onClick={onClose} className="btn-secondary">Cancel</button>
    </form>
  )
}

// --- Main Page ---
export default function Leave() {
  const queryClient = useQueryClient()
  const now = new Date()
  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth())
  const [showAddLeave, setShowAddLeave] = useState(false)
  const [showAddHoliday, setShowAddHoliday] = useState(false)
  const [deleteLeave, setDeleteLeave] = useState(null)
  const [deleteHoliday, setDeleteHoliday] = useState(null)

  const { data: leaveData, isLoading: leavesLoading } = useQuery({
    queryKey: ['leaves'],
    queryFn: () => api.get('/leave').then((r) => r.data),
  })

  const { data: holidayData } = useQuery({
    queryKey: ['holidays'],
    queryFn: () => api.get('/holidays').then((r) => r.data),
  })

  const { data: employeeData } = useQuery({
    queryKey: ['employees'],
    queryFn: () => api.get('/employees').then((r) => r.data),
  })

  const { data: calendarData } = useQuery({
    queryKey: ['attendance', 'calendar', year, month],
    queryFn: () =>
      api
        .get('/attendance/calendar', { params: { year, month: month + 1 } })
        .then((r) => r.data),
  })

  const deleteLeaveMutation = useMutation({
    mutationFn: (id) => api.delete(`/leave/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['leaves'] })
      setDeleteLeave(null)
    },
  })

  const deleteHolidayMutation = useMutation({
    mutationFn: (id) => api.delete(`/holidays/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['holidays'] })
      setDeleteHoliday(null)
    },
  })

  const leaves = leaveData?.leaves || (Array.isArray(leaveData) ? leaveData : [])
  const holidays = holidayData?.holidays || (Array.isArray(holidayData) ? holidayData : [])
  const employees = employeeData?.employees || (Array.isArray(employeeData) ? employeeData : [])

  // Build day statuses for calendar
  const dayStatuses = useMemo(() => {
    const statuses = {}
    // From calendar API data
    if (calendarData?.days) {
      Object.entries(calendarData.days).forEach(([date, status]) => {
        statuses[date] = status
      })
    }
    // Add holidays
    holidays.forEach((h) => {
      if (h.date) statuses[h.date] = 'holiday'
    })
    // Add leaves
    leaves.forEach((l) => {
      const start = new Date(l.start_date || l.date)
      const end = new Date(l.end_date || l.date)
      for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
        const key = d.toISOString().split('T')[0]
        statuses[key] = 'leave'
      }
    })
    return statuses
  }, [calendarData, holidays, leaves])

  const handleChangeMonth = useCallback((y, m) => {
    setYear(y)
    setMonth(m)
  }, [])

  function formatDate(d) {
    if (!d) return '--'
    try {
      return new Date(d).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
    } catch {
      return d
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Leave Management</h1>
          <p className="text-sm text-gray-500 mt-1">Manage employee leave and holidays</p>
        </div>
        <button
          onClick={() => setShowAddLeave(!showAddLeave)}
          className={showAddLeave ? 'btn-secondary' : 'btn-primary'}
        >
          {showAddLeave ? (
            <><X className="w-4 h-4 mr-1" /> Cancel</>
          ) : (
            <><Plus className="w-4 h-4 mr-1" /> Add Leave</>
          )}
        </button>
      </div>

      {/* Add Leave Form */}
      {showAddLeave && (
        <AddLeaveForm employees={employees} onClose={() => setShowAddLeave(false)} />
      )}

      {/* Calendar */}
      <CalendarView
        year={year}
        month={month}
        onChangeMonth={handleChangeMonth}
        dayStatuses={dayStatuses}
        leaves={leaves}
        holidays={holidays}
      />

      {/* Leave Records Table */}
      <div className="card">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Leave Records</h3>
        {leavesLoading ? (
          <SkeletonTable rows={4} cols={5} />
        ) : leaves.length === 0 ? (
          <EmptyState
            icon={Calendar}
            title="No leave records"
            description="Add leave entries using the form above."
          />
        ) : (
          <div className="overflow-x-auto -mx-4 sm:-mx-6">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider border-b border-gray-100">
                  <th className="py-3 px-4">Employee</th>
                  <th className="py-3 px-4">Date</th>
                  <th className="py-3 px-4">Type</th>
                  <th className="py-3 px-4">Note</th>
                  <th className="py-3 px-4">Actions</th>
                </tr>
              </thead>
              <tbody>
                {leaves.map((leave) => (
                  <tr key={leave.id} className="border-b border-gray-50 last:border-0 hover:bg-gray-50">
                    <td className="py-3 px-4 font-medium text-gray-900">
                      {leave.employee_name || leave.name || '--'}
                    </td>
                    <td className="py-3 px-4 text-gray-600">
                      {formatDate(leave.start_date || leave.date)}
                      {leave.end_date && leave.end_date !== leave.start_date && (
                        <> - {formatDate(leave.end_date)}</>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <span className="inline-flex px-2 py-0.5 text-xs font-medium rounded-full bg-blue-50 text-blue-700">
                        {leave.leave_type || leave.type || leave.reason || '--'}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-gray-500 max-w-48 truncate">
                      {leave.note || leave.reason || '--'}
                    </td>
                    <td className="py-3 px-4">
                      <button
                        onClick={() => setDeleteLeave(leave)}
                        className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg"
                        aria-label="Delete leave"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Holiday Management */}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
            <Star className="w-4 h-4" />
            Holiday Management
          </h3>
          {!showAddHoliday && (
            <button onClick={() => setShowAddHoliday(true)} className="btn-primary text-xs px-3 py-1.5">
              <Plus className="w-3.5 h-3.5 mr-1" />
              Add Holiday
            </button>
          )}
        </div>

        {showAddHoliday && (
          <div className="mb-4 pb-4 border-b border-gray-100">
            <AddHolidayForm onClose={() => setShowAddHoliday(false)} />
          </div>
        )}

        {holidays.length === 0 ? (
          <p className="text-sm text-gray-500 text-center py-4">No holidays configured.</p>
        ) : (
          <div className="space-y-2">
            {holidays.map((h) => (
              <div
                key={h.id}
                className="flex items-center justify-between py-2.5 px-3 bg-purple-50 rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <span className="w-2 h-2 rounded-full bg-purple-500" />
                  <div>
                    <p className="text-sm font-medium text-gray-800">{h.name}</p>
                    <p className="text-xs text-gray-500">{formatDate(h.date)}</p>
                  </div>
                </div>
                <button
                  onClick={() => setDeleteHoliday(h)}
                  className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg"
                  aria-label={`Delete ${h.name}`}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Confirm Dialogs */}
      <ConfirmDialog
        open={!!deleteLeave}
        onClose={() => setDeleteLeave(null)}
        onConfirm={() => deleteLeaveMutation.mutate(deleteLeave.id)}
        title="Delete Leave Record"
        message="Are you sure you want to delete this leave record?"
        confirmText="Delete"
        destructive
        loading={deleteLeaveMutation.isPending}
      />

      <ConfirmDialog
        open={!!deleteHoliday}
        onClose={() => setDeleteHoliday(null)}
        onConfirm={() => deleteHolidayMutation.mutate(deleteHoliday.id)}
        title="Delete Holiday"
        message={`Are you sure you want to remove "${deleteHoliday?.name}" from the holiday list?`}
        confirmText="Delete"
        destructive
        loading={deleteHolidayMutation.isPending}
      />
    </div>
  )
}
