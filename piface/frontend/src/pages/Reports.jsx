import React, { useState, useMemo, useCallback, lazy, Suspense } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { api } from '../api/client'
import { SkeletonTable } from '../components/Skeleton'
import EmptyState from '../components/EmptyState'
import {
  BarChart3,
  Download,
  FileSpreadsheet,
  FileText,
  Calendar,
  ArrowUpDown,
  ChevronDown,
} from 'lucide-react'

// Lazy load recharts components
const LazyBarChart = lazy(() =>
  import('recharts').then((mod) => ({
    default: function BarChartWrapper({ data }) {
      const { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend } = mod
      return (
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 5, right: 5, left: -20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f0f0f0" />
            <XAxis dataKey="date" tick={{ fontSize: 12 }} tickLine={false} />
            <YAxis tick={{ fontSize: 12 }} tickLine={false} axisLine={false} />
            <Tooltip />
            <Legend />
            <Bar dataKey="present" fill="#22c55e" name="Present" radius={[4, 4, 0, 0]} />
            <Bar dataKey="absent" fill="#ef4444" name="Absent" radius={[4, 4, 0, 0]} />
            <Bar dataKey="leave" fill="#3b82f6" name="Leave" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )
    },
  }))
)

const LazyPieChart = lazy(() =>
  import('recharts').then((mod) => ({
    default: function PieChartWrapper({ data }) {
      const { ResponsiveContainer, PieChart, Pie, Cell, Legend, Tooltip } = mod
      const COLORS = ['#22c55e', '#ef4444', '#3b82f6']
      return (
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={50}
              outerRadius={80}
              paddingAngle={3}
              dataKey="value"
              label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
            >
              {data.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      )
    },
  }))
)

function formatDate(d) {
  if (!d) return '--'
  try {
    return new Date(d).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
  } catch {
    return d
  }
}

function todayStr() {
  return new Date().toISOString().split('T')[0]
}

function startOfWeek() {
  const d = new Date()
  d.setDate(d.getDate() - d.getDay())
  return d.toISOString().split('T')[0]
}

function startOfMonth() {
  const d = new Date()
  d.setDate(1)
  return d.toISOString().split('T')[0]
}

function startOfLastMonth() {
  const d = new Date()
  d.setMonth(d.getMonth() - 1, 1)
  return d.toISOString().split('T')[0]
}

function endOfLastMonth() {
  const d = new Date()
  d.setDate(0)
  return d.toISOString().split('T')[0]
}

export default function Reports() {
  const [dateFrom, setDateFrom] = useState(startOfWeek())
  const [dateTo, setDateTo] = useState(todayStr())
  const [activeTab, setActiveTab] = useState('summary')
  const [sortCol, setSortCol] = useState(null)
  const [sortDir, setSortDir] = useState('asc')

  const setPreset = useCallback((preset) => {
    switch (preset) {
      case 'today':
        setDateFrom(todayStr())
        setDateTo(todayStr())
        break
      case 'week':
        setDateFrom(startOfWeek())
        setDateTo(todayStr())
        break
      case 'month':
        setDateFrom(startOfMonth())
        setDateTo(todayStr())
        break
      case 'last_month':
        setDateFrom(startOfLastMonth())
        setDateTo(endOfLastMonth())
        break
    }
  }, [])

  const { data: reportData, isLoading } = useQuery({
    queryKey: ['reports', dateFrom, dateTo],
    queryFn: () =>
      api.get('/reports', { params: { date_from: dateFrom, date_to: dateTo } }).then((r) => r.data),
    enabled: !!dateFrom && !!dateTo,
  })

  const { data: historyData } = useQuery({
    queryKey: ['reports', 'history'],
    queryFn: () => api.get('/reports/history').then((r) => r.data),
  })

  const downloadExcelMutation = useMutation({
    mutationFn: () => {
      window.open(`/api/reports/download/excel?date_from=${dateFrom}&date_to=${dateTo}`, '_blank')
    },
  })

  const downloadPdfMutation = useMutation({
    mutationFn: () => {
      window.open(`/api/reports/download/pdf?date_from=${dateFrom}&date_to=${dateTo}`, '_blank')
    },
  })

  const summaryRows = reportData?.summary || reportData?.employees || []
  const chartData = reportData?.chart_data || reportData?.daily || []
  const pieData = useMemo(() => {
    const s = reportData?.breakdown || {}
    return [
      { name: 'Present', value: s.present || 0 },
      { name: 'Absent', value: s.absent || 0 },
      { name: 'Leave', value: s.leave || 0 },
    ].filter((d) => d.value > 0)
  }, [reportData])

  const sortedRows = useMemo(() => {
    if (!sortCol || !summaryRows.length) return summaryRows
    const sorted = [...summaryRows].sort((a, b) => {
      const aVal = a[sortCol] ?? 0
      const bVal = b[sortCol] ?? 0
      if (typeof aVal === 'string') return aVal.localeCompare(bVal)
      return aVal - bVal
    })
    return sortDir === 'desc' ? sorted.reverse() : sorted
  }, [summaryRows, sortCol, sortDir])

  const handleSort = useCallback(
    (col) => {
      if (sortCol === col) {
        setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
      } else {
        setSortCol(col)
        setSortDir('asc')
      }
    },
    [sortCol]
  )

  const reportHistory = historyData?.reports || historyData || []

  function SortHeader({ col, label }) {
    return (
      <th
        className="py-3 px-4 cursor-pointer select-none hover:bg-gray-50"
        onClick={() => handleSort(col)}
      >
        <div className="flex items-center gap-1">
          {label}
          <ArrowUpDown className="w-3 h-3 text-gray-400" />
        </div>
      </th>
    )
  }

  function coloredCell(value, thresholds) {
    if (value == null) return 'text-gray-500'
    if (thresholds.bad && value >= thresholds.bad) return 'text-red-600 font-semibold'
    if (thresholds.warn && value >= thresholds.warn) return 'text-amber-600'
    if (thresholds.good && value >= thresholds.good) return 'text-green-600'
    return 'text-gray-700'
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Reports & Analytics</h1>
        <p className="text-sm text-gray-500 mt-1">Attendance insights and downloadable reports</p>
      </div>

      {/* Date Range Selector */}
      <div className="card">
        <div className="flex flex-col sm:flex-row sm:items-end gap-4">
          <div className="flex gap-3 flex-1">
            <div className="flex-1">
              <label htmlFor="rpt-from" className="label">From</label>
              <input
                id="rpt-from"
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="input"
              />
            </div>
            <div className="flex-1">
              <label htmlFor="rpt-to" className="label">To</label>
              <input
                id="rpt-to"
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="input"
              />
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            {[
              { key: 'today', label: 'Today' },
              { key: 'week', label: 'This Week' },
              { key: 'month', label: 'This Month' },
              { key: 'last_month', label: 'Last Month' },
            ].map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setPreset(key)}
                className="px-3 py-1.5 text-xs font-medium rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-50 transition-colors"
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-200">
        {[
          { key: 'summary', label: 'Summary Table' },
          { key: 'charts', label: 'Charts' },
        ].map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              activeTab === key
                ? 'border-primary-600 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Summary Table Tab */}
      {activeTab === 'summary' && (
        <>
          {isLoading ? (
            <div className="card">
              <SkeletonTable rows={5} cols={6} />
            </div>
          ) : sortedRows.length === 0 ? (
            <EmptyState
              icon={BarChart3}
              title="No report data"
              description="Select a date range to generate a report."
            />
          ) : (
            <div className="card p-0 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider border-b border-gray-100">
                    <SortHeader col="name" label="Employee" />
                    <SortHeader col="days_present" label="Days Present" />
                    <SortHeader col="total_hours" label="Total Hours" />
                    <SortHeader col="avg_arrival" label="Avg Arrival" />
                    <SortHeader col="late_days" label="Late Days" />
                    <SortHeader col="absences" label="Absences" />
                  </tr>
                </thead>
                <tbody>
                  {sortedRows.map((row, i) => (
                    <tr key={row.id || i} className="border-b border-gray-50 last:border-0 hover:bg-gray-50">
                      <td className="py-3 px-4 font-medium text-gray-900">{row.name || '--'}</td>
                      <td className={`py-3 px-4 ${coloredCell(row.days_present, { good: 1 })}`}>
                        {row.days_present ?? '--'}
                      </td>
                      <td className="py-3 px-4 text-gray-700">
                        {row.total_hours != null ? `${row.total_hours}h` : '--'}
                      </td>
                      <td className="py-3 px-4 text-gray-700">{row.avg_arrival || '--'}</td>
                      <td className={`py-3 px-4 ${coloredCell(row.late_days, { warn: 3, bad: 5 })}`}>
                        {row.late_days ?? '--'}
                      </td>
                      <td className={`py-3 px-4 ${coloredCell(row.absences, { warn: 2, bad: 4 })}`}>
                        {row.absences ?? '--'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* Charts Tab */}
      {activeTab === 'charts' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="card">
            <h3 className="text-sm font-semibold text-gray-700 mb-4">Daily Attendance</h3>
            {isLoading ? (
              <div className="h-64 flex items-center justify-center">
                <div className="w-6 h-6 border-2 border-gray-300 border-t-primary-600 rounded-full animate-spin" />
              </div>
            ) : chartData.length === 0 ? (
              <div className="h-64 flex items-center justify-center text-sm text-gray-500">
                No chart data available.
              </div>
            ) : (
              <div className="h-64 sm:h-80">
                <Suspense
                  fallback={
                    <div className="h-full flex items-center justify-center">
                      <div className="w-6 h-6 border-2 border-gray-300 border-t-primary-600 rounded-full animate-spin" />
                    </div>
                  }
                >
                  <LazyBarChart data={chartData} />
                </Suspense>
              </div>
            )}
          </div>

          <div className="card">
            <h3 className="text-sm font-semibold text-gray-700 mb-4">Attendance Breakdown</h3>
            {isLoading ? (
              <div className="h-64 flex items-center justify-center">
                <div className="w-6 h-6 border-2 border-gray-300 border-t-primary-600 rounded-full animate-spin" />
              </div>
            ) : pieData.length === 0 ? (
              <div className="h-64 flex items-center justify-center text-sm text-gray-500">
                No breakdown data available.
              </div>
            ) : (
              <div className="h-64 sm:h-80">
                <Suspense
                  fallback={
                    <div className="h-full flex items-center justify-center">
                      <div className="w-6 h-6 border-2 border-gray-300 border-t-primary-600 rounded-full animate-spin" />
                    </div>
                  }
                >
                  <LazyPieChart data={pieData} />
                </Suspense>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Download Section */}
      <div className="card">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Download Report</h3>
        <p className="text-xs text-gray-500 mb-4">
          {dateFrom && dateTo
            ? `Report for ${formatDate(dateFrom)} - ${formatDate(dateTo)}`
            : 'Select a date range above'}
        </p>
        <div className="flex flex-wrap gap-3">
          <button
            onClick={() => downloadExcelMutation.mutate()}
            disabled={!dateFrom || !dateTo}
            className="btn-primary text-sm"
          >
            {downloadExcelMutation.isPending ? (
              <>
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                Generating...
              </>
            ) : (
              <>
                <FileSpreadsheet className="w-4 h-4 mr-2" />
                Download Excel
              </>
            )}
          </button>
          <button
            onClick={() => downloadPdfMutation.mutate()}
            disabled={!dateFrom || !dateTo}
            className="btn-secondary text-sm"
          >
            {downloadPdfMutation.isPending ? (
              <>
                <span className="w-4 h-4 border-2 border-gray-300 border-t-gray-600 rounded-full animate-spin mr-2" />
                Generating...
              </>
            ) : (
              <>
                <FileText className="w-4 h-4 mr-2" />
                Download PDF
              </>
            )}
          </button>
        </div>
      </div>

      {/* Report History */}
      <div className="card">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Report History</h3>
        {reportHistory.length === 0 ? (
          <p className="text-sm text-gray-500 text-center py-4">No past reports generated yet.</p>
        ) : (
          <div className="space-y-2">
            {reportHistory.map((rpt, i) => (
              <div
                key={rpt.id || i}
                className="flex items-center justify-between py-3 px-4 bg-gray-50 rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <Calendar className="w-4 h-4 text-gray-400" />
                  <div>
                    <p className="text-sm font-medium text-gray-700">
                      {formatDate(rpt.date_from || rpt.date)} - {formatDate(rpt.date_to || rpt.date)}
                    </p>
                    <p className="text-xs text-gray-500">
                      Generated {formatDate(rpt.created_at || rpt.generated_at)}
                    </p>
                  </div>
                </div>
                <div className="flex gap-2">
                  {rpt.excel_url && (
                    <a
                      href={rpt.excel_url}
                      download
                      className="p-1.5 text-gray-400 hover:text-green-600 rounded-lg"
                      aria-label="Download Excel"
                    >
                      <FileSpreadsheet className="w-4 h-4" />
                    </a>
                  )}
                  {rpt.pdf_url && (
                    <a
                      href={rpt.pdf_url}
                      download
                      className="p-1.5 text-gray-400 hover:text-red-600 rounded-lg"
                      aria-label="Download PDF"
                    >
                      <FileText className="w-4 h-4" />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
