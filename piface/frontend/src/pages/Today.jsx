import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import StatusBadge from '../components/StatusBadge'
import LiveFeed from '../components/LiveFeed'
import { SkeletonCard, SkeletonTable } from '../components/Skeleton'
import EmptyState from '../components/EmptyState'
import {
  Users,
  UserX,
  Palmtree,
  Clock,
  ArrowDownCircle,
  ArrowUpCircle,
  Activity,
} from 'lucide-react'

// --- SSE hook for live events ---
function useSSE(url) {
  const [events, setEvents] = useState([])
  const eventSourceRef = useRef(null)

  useEffect(() => {
    const es = new EventSource(url)
    eventSourceRef.current = es

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        setEvents((prev) => [data, ...prev].slice(0, 10))
      } catch {
        // ignore malformed messages
      }
    }

    es.onerror = () => {
      es.close()
      // Reconnect after 5s
      setTimeout(() => {
        if (eventSourceRef.current === es) {
          const newEs = new EventSource(url)
          eventSourceRef.current = newEs
          newEs.onmessage = es.onmessage
          newEs.onerror = es.onerror
        }
      }, 5000)
    }

    return () => {
      es.close()
      eventSourceRef.current = null
    }
  }, [url])

  return events
}

// --- Initials Avatar ---
function InitialsAvatar({ name, className = '' }) {
  const initials = (name || '?')
    .split(' ')
    .map((w) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)

  return (
    <div
      className={`flex items-center justify-center rounded-full bg-primary-100 text-primary-700 font-semibold text-sm ${className}`}
      aria-hidden="true"
    >
      {initials}
    </div>
  )
}

// --- Stat Card ---
function StatCard({ icon: Icon, label, value, color, loading }) {
  const colorMap = {
    green: 'bg-green-50 text-green-600',
    red: 'bg-red-50 text-red-600',
    blue: 'bg-blue-50 text-blue-600',
    amber: 'bg-amber-50 text-amber-600',
  }

  return (
    <div className="card flex items-center gap-3">
      <div className={`p-2.5 rounded-lg ${colorMap[color] || colorMap.blue}`}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-xs text-gray-500 font-medium">{label}</p>
        {loading ? (
          <div className="animate-pulse bg-gray-200 rounded h-6 w-12 mt-1" />
        ) : (
          <p className="text-xl font-bold text-gray-900">{value ?? '--'}</p>
        )}
      </div>
    </div>
  )
}

// --- Map API status to badge variant ---
function statusToVariant(status) {
  const map = {
    in: 'in',
    IN: 'in',
    present: 'in',
    break: 'break',
    Break: 'break',
    out: 'out',
    OUT: 'out',
    left: 'out',
    not_arrived: 'not_arrived',
    absent: 'not_arrived',
    on_leave: 'on_leave',
    leave: 'on_leave',
  }
  return map[status] || 'out'
}

function formatTime(t) {
  if (!t) return '--'
  try {
    const d = new Date(t)
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  } catch {
    return t
  }
}

function formatHours(h) {
  if (h == null) return '--'
  const hrs = Math.floor(h)
  const mins = Math.round((h - hrs) * 60)
  return `${hrs}h ${mins}m`
}

// --- Employee Row (table) ---
function EmployeeRow({ emp }) {
  return (
    <tr className="border-b border-gray-100 last:border-0 hover:bg-gray-50 transition-colors">
      <td className="py-3 px-4">
        <div className="flex items-center gap-3">
          <InitialsAvatar name={emp.name} className="w-8 h-8" />
          <div>
            <p className="text-sm font-medium text-gray-900">{emp.name}</p>
            <p className="text-xs text-gray-500">{emp.department || '--'}</p>
          </div>
        </div>
      </td>
      <td className="py-3 px-4">
        <StatusBadge status={statusToVariant(emp.status)} />
      </td>
      <td className="py-3 px-4 text-sm text-gray-600">{formatTime(emp.first_in)}</td>
      <td className="py-3 px-4 text-sm text-gray-600">{formatHours(emp.hours)}</td>
    </tr>
  )
}

// --- Employee Card (mobile) ---
function EmployeeCard({ emp }) {
  return (
    <div className="card flex items-center gap-3">
      <InitialsAvatar name={emp.name} className="w-10 h-10 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <p className="text-sm font-medium text-gray-900 truncate">{emp.name}</p>
          <StatusBadge status={statusToVariant(emp.status)} />
        </div>
        <p className="text-xs text-gray-500 mt-0.5">{emp.department || '--'}</p>
        <div className="flex items-center gap-4 mt-1 text-xs text-gray-500">
          <span>In: {formatTime(emp.first_in)}</span>
          <span>Hours: {formatHours(emp.hours)}</span>
        </div>
      </div>
    </div>
  )
}

// --- Recent Event Item ---
function EventItem({ event }) {
  const isIn =
    event.event_type === 'IN' ||
    event.event_type === 'in' ||
    event.event_type === 'check_in'

  return (
    <div
      className={`flex items-center gap-2 py-1.5 px-2 rounded text-sm ${
        isIn ? 'text-green-700' : 'text-red-700'
      }`}
    >
      {isIn ? (
        <ArrowDownCircle className="w-3.5 h-3.5 flex-shrink-0" />
      ) : (
        <ArrowUpCircle className="w-3.5 h-3.5 flex-shrink-0" />
      )}
      <span className="truncate">
        <span className="font-medium">{event.person_name || 'Unknown'}</span>
        {' checked '}
        <span className="font-semibold">{isIn ? 'IN' : 'OUT'}</span>
        {event.timestamp && (
          <span className="text-gray-500"> at {formatTime(event.timestamp)}</span>
        )}
      </span>
    </div>
  )
}

// --- Main Page ---
export default function Today() {
  const {
    data: todayData,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['attendance', 'today'],
    queryFn: () => api.get('/attendance/today').then((r) => r.data),
    refetchInterval: 30000,
    refetchIntervalInBackground: false,
  })

  const liveEvents = useSSE('/api/attendance/live')

  const employees = todayData?.employees || []
  const summary = todayData?.summary || {}

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Today's Attendance</h1>
        <p className="text-sm text-gray-500 mt-1">
          {new Date().toLocaleDateString(undefined, {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric',
          })}
        </p>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <StatCard
          icon={Users}
          label="Present"
          value={summary.total_present}
          color="green"
          loading={isLoading}
        />
        <StatCard
          icon={UserX}
          label="Absent"
          value={summary.total_absent}
          color="red"
          loading={isLoading}
        />
        <StatCard
          icon={Palmtree}
          label="On Leave"
          value={summary.on_leave}
          color="blue"
          loading={isLoading}
        />
        <StatCard
          icon={Clock}
          label="Avg Hours"
          value={summary.average_hours != null ? `${summary.average_hours}h` : undefined}
          color="amber"
          loading={isLoading}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Employee Status List */}
        <div className="lg:col-span-2">
          <div className="card p-0 sm:p-0">
            <div className="px-4 sm:px-6 py-4 border-b border-gray-100">
              <h2 className="text-base font-semibold text-gray-900">Employee Status</h2>
            </div>

            {isLoading ? (
              <div className="p-4 sm:p-6">
                <div className="hidden sm:block">
                  <SkeletonTable rows={5} cols={4} />
                </div>
                <div className="sm:hidden space-y-3">
                  {Array.from({ length: 4 }).map((_, i) => (
                    <SkeletonCard key={i} />
                  ))}
                </div>
              </div>
            ) : error ? (
              <div className="p-6 text-center text-red-600 text-sm">
                Failed to load attendance data. Please try again.
              </div>
            ) : employees.length === 0 ? (
              <EmptyState
                icon={Users}
                title="No employees found"
                description="Employee data will appear here once people are registered."
              />
            ) : (
              <>
                {/* Desktop Table */}
                <div className="hidden sm:block overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider border-b border-gray-100">
                        <th className="py-3 px-4">Employee</th>
                        <th className="py-3 px-4">Status</th>
                        <th className="py-3 px-4">First In</th>
                        <th className="py-3 px-4">Hours</th>
                      </tr>
                    </thead>
                    <tbody>
                      {employees.map((emp) => (
                        <EmployeeRow key={emp.id || emp.employee_id} emp={emp} />
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Mobile Cards */}
                <div className="sm:hidden p-4 space-y-3">
                  {employees.map((emp) => (
                    <EmployeeCard key={emp.id || emp.employee_id} emp={emp} />
                  ))}
                </div>
              </>
            )}
          </div>
        </div>

        {/* Sidebar: Recent Events */}
        <div className="space-y-6">
          {/* Recent Events Ticker */}
          <div className="card">
            <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2 mb-3">
              <Activity className="w-4 h-4" />
              Recent Events
            </h3>
            {liveEvents.length === 0 ? (
              <p className="text-xs text-gray-500 text-center py-4">
                Waiting for live events...
              </p>
            ) : (
              <div className="space-y-1 max-h-60 overflow-y-auto">
                {liveEvents.map((evt, i) => (
                  <EventItem key={evt.id || i} event={evt} />
                ))}
              </div>
            )}
          </div>

          {/* Live Camera Feed - collapsed by default on mobile */}
          <div className="hidden lg:block">
            <LiveFeed />
          </div>
        </div>
      </div>

      {/* Mobile Live Feed - collapsible */}
      <div className="lg:hidden">
        <LiveFeed />
      </div>
    </div>
  )
}
