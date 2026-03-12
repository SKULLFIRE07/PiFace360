import React, { useState, useEffect, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import ConfirmDialog from '../components/ConfirmDialog'
import { SkeletonText } from '../components/Skeleton'
import {
  Building2,
  Clock,
  Wifi,
  Lock,
  ScanFace,
  Database,
  Activity,
  HardDrive,
  RefreshCw,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Save,
  CheckCircle,
  Thermometer,
  Camera,
  Cpu,
  Shield,
  Server,
} from 'lucide-react'

// --- Section Group Header ---
function SectionGroup({ icon: Icon, title }) {
  return (
    <div className="flex items-center gap-2 pt-4 pb-1">
      <Icon className="w-4 h-4 text-gray-400" />
      <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-400">{title}</h2>
    </div>
  )
}

// --- Collapsible Section ---
function Section({ id, icon: Icon, title, children, defaultOpen = false, danger = false }) {
  const [open, setOpen] = useState(defaultOpen)

  return (
    <div id={id} className={`card ${danger ? 'border-2 border-red-300 ring-1 ring-red-100' : ''}`}>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between text-left"
      >
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${danger ? 'bg-red-50' : 'bg-gray-100'}`}>
            <Icon className={`w-4 h-4 ${danger ? 'text-red-500' : 'text-gray-600'}`} />
          </div>
          <h3 className={`text-sm font-semibold ${danger ? 'text-red-700' : 'text-gray-900'}`}>{title}</h3>
        </div>
        {open ? (
          <ChevronUp className="w-4 h-4 text-gray-400" />
        ) : (
          <ChevronDown className="w-4 h-4 text-gray-400" />
        )}
      </button>
      {open && <div className="mt-4 pt-4 border-t border-gray-100">{children}</div>}
    </div>
  )
}

// --- Success Toast ---
function SuccessMsg({ message, onDone }) {
  useEffect(() => {
    const t = setTimeout(onDone, 3000)
    return () => clearTimeout(t)
  }, [onDone])

  return (
    <div className="flex items-center gap-2 p-3 rounded-lg bg-green-50 text-green-700 text-sm mb-4">
      <CheckCircle className="w-4 h-4 flex-shrink-0" />
      <span>{message}</span>
    </div>
  )
}

// --- System Status Display ---
function SystemStatus() {
  const { data, isLoading } = useQuery({
    queryKey: ['system', 'status'],
    queryFn: () => api.get('/system/status').then((r) => r.data),
    refetchInterval: 10000,
  })

  if (isLoading) return <SkeletonText lines={4} />

  const status = data || {}

  function statusColor(key) {
    const thresholds = {
      cpu_temp: { warn: 65, bad: 75 },
      disk_free_pct: { bad: 10, warn: 20 },
    }
    const t = thresholds[key]
    if (!t) return 'text-green-600'
    const val = status[key]
    if (val == null) return 'text-gray-500'
    if (key === 'disk_free_pct') {
      if (val <= t.bad) return 'text-red-600'
      if (val <= t.warn) return 'text-amber-600'
      return 'text-green-600'
    }
    if (val >= t.bad) return 'text-red-600'
    if (val >= t.warn) return 'text-amber-600'
    return 'text-green-600'
  }

  const items = [
    { label: 'Uptime', value: status.uptime || '--', icon: Clock },
    { label: 'Database Size', value: status.db_size || '--', icon: Database },
    {
      label: 'Disk Free',
      value: status.disk_free || status.disk_free_pct != null ? `${status.disk_free_pct}%` : '--',
      icon: HardDrive,
      colorKey: 'disk_free_pct',
    },
    {
      label: 'CPU Temp',
      value: status.cpu_temp != null ? `${status.cpu_temp}C` : '--',
      icon: Thermometer,
      colorKey: 'cpu_temp',
    },
    {
      label: 'Camera',
      value: status.camera_status || '--',
      icon: Camera,
    },
    {
      label: 'Last Detection',
      value: status.last_detection
        ? new Date(status.last_detection).toLocaleTimeString()
        : '--',
      icon: ScanFace,
    },
  ]

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
          <item.icon className={`w-4 h-4 ${item.colorKey ? statusColor(item.colorKey) : 'text-gray-500'}`} />
          <div>
            <p className="text-xs text-gray-500">{item.label}</p>
            <p className={`text-sm font-medium ${item.colorKey ? statusColor(item.colorKey) : 'text-gray-900'}`}>
              {item.value}
            </p>
          </div>
        </div>
      ))}
    </div>
  )
}

// --- Main Page ---
export default function Settings() {
  const queryClient = useQueryClient()
  const { data: settings, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: () => api.get('/settings').then((r) => r.data),
  })

  // Company Info
  const [companyName, setCompanyName] = useState('')
  const [companySaved, setCompanySaved] = useState(false)

  useEffect(() => {
    if (settings?.company_name) setCompanyName(settings.company_name)
  }, [settings])

  const companyMutation = useMutation({
    mutationFn: (data) => api.put('/settings', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
      setCompanySaved(true)
    },
  })

  // Working Hours
  const [shiftStart, setShiftStart] = useState('09:00')
  const [shiftEnd, setShiftEnd] = useState('18:00')
  const [lateThreshold, setLateThreshold] = useState(15)
  const [weekendDays, setWeekendDays] = useState([0, 6])
  const [hoursSaved, setHoursSaved] = useState(false)

  useEffect(() => {
    if (settings) {
      setShiftStart(settings.shift_start || '09:00')
      setShiftEnd(settings.shift_end || '18:00')
      setLateThreshold(settings.late_threshold_minutes ?? 15)
      setWeekendDays(settings.weekend_days || [0, 6])
    }
  }, [settings])

  const hoursMutation = useMutation({
    mutationFn: (data) => api.put('/settings', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
      setHoursSaved(true)
    },
  })

  const toggleWeekendDay = useCallback((day) => {
    setWeekendDays((prev) =>
      prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day]
    )
  }, [])

  // WiFi
  const [ssid, setSsid] = useState('')
  const [wifiPassword, setWifiPassword] = useState('')
  const [wifiSaved, setWifiSaved] = useState(false)
  const [showWifiWarn, setShowWifiWarn] = useState(false)

  const wifiMutation = useMutation({
    mutationFn: (data) => api.put('/settings/wifi', data),
    onSuccess: () => {
      setWifiSaved(true)
      setShowWifiWarn(false)
    },
  })

  // Admin Password
  const [currentPw, setCurrentPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirmPw, setConfirmPw] = useState('')
  const [pwSaved, setPwSaved] = useState(false)
  const [pwError, setPwError] = useState('')

  const pwMutation = useMutation({
    mutationFn: (data) => api.put('/settings/password', data),
    onSuccess: () => {
      setPwSaved(true)
      setCurrentPw('')
      setNewPw('')
      setConfirmPw('')
      setPwError('')
    },
    onError: (err) => {
      setPwError(err.response?.data?.detail || 'Failed to update password.')
    },
  })

  // Face Recognition
  const [threshold, setThreshold] = useState(0.6)
  const [thresholdSaved, setThresholdSaved] = useState(false)

  useEffect(() => {
    if (settings?.similarity_threshold != null) setThreshold(settings.similarity_threshold)
  }, [settings])

  const thresholdMutation = useMutation({
    mutationFn: (data) => api.put('/settings', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
      setThresholdSaved(true)
    },
  })

  // Data Retention
  const [snapshotDays, setSnapshotDays] = useState(30)
  const [reportDays, setReportDays] = useState(90)
  const [retentionSaved, setRetentionSaved] = useState(false)

  useEffect(() => {
    if (settings) {
      setSnapshotDays(settings.snapshot_retention_days ?? 30)
      setReportDays(settings.report_retention_days ?? 90)
    }
  }, [settings])

  const retentionMutation = useMutation({
    mutationFn: (data) => api.put('/settings', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
      setRetentionSaved(true)
    },
  })

  // Backup
  const backupMutation = useMutation({
    mutationFn: () => api.post('/system/backup'),
  })

  // Restart Services
  const [showRestartFace, setShowRestartFace] = useState(false)
  const [showRestartLed, setShowRestartLed] = useState(false)

  const restartFaceMutation = useMutation({
    mutationFn: () => api.post('/system/restart/face-engine'),
  })

  const restartLedMutation = useMutation({
    mutationFn: () => api.post('/system/restart/led-controller'),
  })

  // Factory Reset
  const [showFactoryReset, setShowFactoryReset] = useState(false)
  const [resetPassword, setResetPassword] = useState('')
  const [resetCountdown, setResetCountdown] = useState(0)

  const factoryResetMutation = useMutation({
    mutationFn: (data) => api.post('/system/factory-reset', data),
    onSuccess: () => {
      window.location.href = '/setup'
    },
  })

  useEffect(() => {
    if (resetCountdown > 0) {
      const t = setTimeout(() => setResetCountdown(resetCountdown - 1), 1000)
      return () => clearTimeout(t)
    }
  }, [resetCountdown])

  const startFactoryReset = useCallback(() => {
    setShowFactoryReset(true)
    setResetCountdown(30)
    setResetPassword('')
  }, [])

  const scrollTo = useCallback((id) => {
    const el = document.getElementById(id)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [])

  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

  if (isLoading) {
    return (
      <div className="space-y-6">
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Settings</h1>
        <div className="space-y-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="card">
              <SkeletonText lines={2} />
            </div>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-sm text-gray-500 mt-1">Manage system configuration</p>
      </div>

      {/* Quick Actions */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => scrollTo('section-system-status')}
          className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-lg bg-gray-100 text-gray-700 hover:bg-gray-200 transition-colors"
        >
          <Activity className="w-3.5 h-3.5" />
          System Status
        </button>
        <button
          onClick={() => backupMutation.mutate()}
          disabled={backupMutation.isPending}
          className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-lg bg-gray-100 text-gray-700 hover:bg-gray-200 transition-colors disabled:opacity-50"
        >
          <HardDrive className="w-3.5 h-3.5" />
          {backupMutation.isPending ? 'Backing up...' : 'Backup Now'}
        </button>
        <button
          onClick={() => scrollTo('section-admin-password')}
          className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium rounded-lg bg-gray-100 text-gray-700 hover:bg-gray-200 transition-colors"
        >
          <Lock className="w-3.5 h-3.5" />
          Change Password
        </button>
      </div>

      {/* ─── General ─── */}
      <SectionGroup icon={Building2} title="General" />

      {/* Company Info */}
      <Section id="section-company-info" icon={Building2} title="Company Info" defaultOpen>
        {companySaved && <SuccessMsg message="Company name saved." onDone={() => setCompanySaved(false)} />}
        <div className="flex gap-3">
          <input
            type="text"
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            className="input flex-1"
            placeholder="Company name"
          />
          <button
            onClick={() => companyMutation.mutate({ company_name: companyName })}
            disabled={companyMutation.isPending}
            className="btn-primary"
          >
            <Save className="w-4 h-4 mr-1" />
            Save
          </button>
        </div>
      </Section>

      {/* Working Hours */}
      <Section id="section-working-hours" icon={Clock} title="Working Hours" defaultOpen>
        {hoursSaved && <SuccessMsg message="Working hours saved." onDone={() => setHoursSaved(false)} />}
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
              <label className="label">Shift Start</label>
              <input type="time" value={shiftStart} onChange={(e) => setShiftStart(e.target.value)} className="input" />
            </div>
            <div>
              <label className="label">Shift End</label>
              <input type="time" value={shiftEnd} onChange={(e) => setShiftEnd(e.target.value)} className="input" />
            </div>
            <div>
              <label className="label">Late Threshold (min)</label>
              <input
                type="number"
                min="0"
                max="120"
                value={lateThreshold}
                onChange={(e) => setLateThreshold(Number(e.target.value))}
                className="input"
              />
            </div>
          </div>
          <div>
            <label className="label">Weekend Days</label>
            <div className="flex flex-wrap gap-2">
              {dayNames.map((day, i) => (
                <button
                  key={i}
                  onClick={() => toggleWeekendDay(i)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                    weekendDays.includes(i)
                      ? 'bg-primary-100 border-primary-300 text-primary-700'
                      : 'bg-white border-gray-300 text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  {day}
                </button>
              ))}
            </div>
          </div>
          <button
            onClick={() =>
              hoursMutation.mutate({
                shift_start: shiftStart,
                shift_end: shiftEnd,
                late_threshold_minutes: lateThreshold,
                weekend_days: weekendDays,
              })
            }
            disabled={hoursMutation.isPending}
            className="btn-primary"
          >
            <Save className="w-4 h-4 mr-1" />
            Save Working Hours
          </button>
        </div>
      </Section>

      {/* WiFi Settings */}
      <Section id="section-wifi" icon={Wifi} title="WiFi Settings">
        {wifiSaved && <SuccessMsg message="WiFi settings saved. Reconnection may be required." onDone={() => setWifiSaved(false)} />}
        <div className="space-y-3">
          <div>
            <label className="label">SSID</label>
            <input type="text" value={ssid} onChange={(e) => setSsid(e.target.value)} className="input" placeholder="Network name" />
          </div>
          <div>
            <label className="label">Password</label>
            <input type="password" value={wifiPassword} onChange={(e) => setWifiPassword(e.target.value)} className="input" placeholder="Network password" />
          </div>
          <div className="flex items-center gap-2 p-3 bg-amber-50 rounded-lg text-xs text-amber-700">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            <span>Changing WiFi settings may cause temporary disconnection from this device.</span>
          </div>
          <button
            onClick={() => {
              if (!showWifiWarn) {
                setShowWifiWarn(true)
                return
              }
              wifiMutation.mutate({ ssid, password: wifiPassword })
            }}
            disabled={wifiMutation.isPending || !ssid}
            className="btn-primary"
          >
            <Save className="w-4 h-4 mr-1" />
            {showWifiWarn ? 'Confirm & Save WiFi' : 'Save WiFi'}
          </button>
        </div>
      </Section>

      {/* ─── Security ─── */}
      <SectionGroup icon={Shield} title="Security" />

      {/* Admin Password */}
      <Section id="section-admin-password" icon={Lock} title="Admin Password">
        {pwSaved && <SuccessMsg message="Password updated successfully." onDone={() => setPwSaved(false)} />}
        {pwError && (
          <div className="flex items-center gap-2 p-3 rounded-lg bg-red-50 text-red-700 text-sm mb-4">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            <span>{pwError}</span>
          </div>
        )}
        <div className="space-y-3 max-w-sm">
          <div>
            <label className="label">Current Password</label>
            <input type="password" value={currentPw} onChange={(e) => setCurrentPw(e.target.value)} className="input" />
          </div>
          <div>
            <label className="label">New Password</label>
            <input type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} className="input" />
          </div>
          <div>
            <label className="label">Confirm New Password</label>
            <input type="password" value={confirmPw} onChange={(e) => setConfirmPw(e.target.value)} className="input" />
          </div>
          <button
            onClick={() => {
              if (newPw !== confirmPw) {
                setPwError('Passwords do not match.')
                return
              }
              if (newPw.length < 4) {
                setPwError('Password must be at least 4 characters.')
                return
              }
              setPwError('')
              pwMutation.mutate({ current_password: currentPw, new_password: newPw })
            }}
            disabled={pwMutation.isPending || !currentPw || !newPw}
            className="btn-primary"
          >
            <Lock className="w-4 h-4 mr-1" />
            Update Password
          </button>
        </div>
      </Section>

      {/* Face Recognition */}
      <Section id="section-face-recognition" icon={ScanFace} title="Face Recognition">
        {thresholdSaved && <SuccessMsg message="Threshold saved." onDone={() => setThresholdSaved(false)} />}
        <div className="space-y-3">
          <div>
            <label className="label">Similarity Threshold: {threshold.toFixed(2)}</label>
            <input
              type="range"
              min="0.4"
              max="0.8"
              step="0.01"
              value={threshold}
              onChange={(e) => setThreshold(Number(e.target.value))}
              className="w-full accent-primary-600"
            />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              <span>0.40 (More matches)</span>
              <span>0.80 (Stricter)</span>
            </div>
          </div>
          <button
            onClick={() => thresholdMutation.mutate({ similarity_threshold: threshold })}
            disabled={thresholdMutation.isPending}
            className="btn-primary"
          >
            <Save className="w-4 h-4 mr-1" />
            Save Threshold
          </button>
        </div>
      </Section>

      {/* ─── System ─── */}
      <SectionGroup icon={Server} title="System" />

      {/* System Status */}
      <Section id="section-system-status" icon={Activity} title="System Status" defaultOpen>
        <SystemStatus />
      </Section>

      {/* Data Retention */}
      <Section id="section-data-retention" icon={Database} title="Data Retention">
        {retentionSaved && <SuccessMsg message="Retention settings saved." onDone={() => setRetentionSaved(false)} />}
        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="label">Snapshot Retention (days)</label>
              <input
                type="number"
                min="1"
                max="365"
                value={snapshotDays}
                onChange={(e) => setSnapshotDays(Number(e.target.value))}
                className="input"
              />
            </div>
            <div>
              <label className="label">Report Retention (days)</label>
              <input
                type="number"
                min="1"
                max="365"
                value={reportDays}
                onChange={(e) => setReportDays(Number(e.target.value))}
                className="input"
              />
            </div>
          </div>
          <button
            onClick={() =>
              retentionMutation.mutate({
                snapshot_retention_days: snapshotDays,
                report_retention_days: reportDays,
              })
            }
            disabled={retentionMutation.isPending}
            className="btn-primary"
          >
            <Save className="w-4 h-4 mr-1" />
            Save Retention
          </button>
        </div>
      </Section>

      {/* Backup */}
      <Section id="section-backup" icon={HardDrive} title="Backup">
        <div className="flex flex-wrap gap-3">
          <button
            onClick={() => backupMutation.mutate()}
            disabled={backupMutation.isPending}
            className="btn-primary"
          >
            {backupMutation.isPending ? (
              <>
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                Creating Backup...
              </>
            ) : (
              <>
                <HardDrive className="w-4 h-4 mr-1" />
                Create Backup
              </>
            )}
          </button>
          {backupMutation.isSuccess && (
            <span className="text-sm text-green-600 flex items-center gap-1">
              <CheckCircle className="w-4 h-4" />
              Backup created successfully
            </span>
          )}
          <a
            href="/api/system/backup/latest"
            download
            className="btn-secondary"
          >
            Download Latest Backup
          </a>
        </div>
      </Section>

      {/* Restart Services */}
      <Section id="section-restart-services" icon={RefreshCw} title="Restart Services">
        <div className="flex flex-wrap gap-3">
          <button onClick={() => setShowRestartFace(true)} className="btn-secondary">
            <RefreshCw className="w-4 h-4 mr-1" />
            Restart Face Engine
          </button>
          <button onClick={() => setShowRestartLed(true)} className="btn-secondary">
            <RefreshCw className="w-4 h-4 mr-1" />
            Restart LED Controller
          </button>
        </div>
      </Section>

      {/* ─── Danger Zone ─── */}
      <SectionGroup icon={AlertTriangle} title="Danger Zone" />

      {/* Factory Reset */}
      <Section id="section-factory-reset" icon={AlertTriangle} title="Factory Reset" danger>
        <div className="space-y-3">
          <p className="text-sm text-gray-600">
            This will erase all data and reset the system to factory defaults. This action cannot be undone.
          </p>
          <button
            onClick={startFactoryReset}
            className="inline-flex items-center justify-center px-4 py-2 bg-red-600 text-white font-medium rounded-lg hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-2 transition-colors"
          >
            <AlertTriangle className="w-4 h-4 mr-1" />
            Factory Reset
          </button>
        </div>
      </Section>

      {/* Confirm Dialogs for Restart */}
      <ConfirmDialog
        open={showRestartFace}
        onClose={() => setShowRestartFace(false)}
        onConfirm={() => {
          restartFaceMutation.mutate()
          setShowRestartFace(false)
        }}
        title="Restart Face Engine"
        message="Are you sure you want to restart the face recognition engine? This will temporarily pause detection."
        confirmText="Restart"
        loading={restartFaceMutation.isPending}
      />

      <ConfirmDialog
        open={showRestartLed}
        onClose={() => setShowRestartLed(false)}
        onConfirm={() => {
          restartLedMutation.mutate()
          setShowRestartLed(false)
        }}
        title="Restart LED Controller"
        message="Are you sure you want to restart the LED controller?"
        confirmText="Restart"
        loading={restartLedMutation.isPending}
      />

      {/* Factory Reset Modal */}
      {showFactoryReset && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" role="dialog" aria-modal="true">
          <div className="fixed inset-0 bg-black/50" onClick={() => setShowFactoryReset(false)} />
          <div className="relative bg-white rounded-xl shadow-xl max-w-md w-full p-6 z-10">
            <h3 className="text-lg font-semibold text-red-600 mb-2">Factory Reset</h3>
            <p className="text-sm text-gray-600 mb-4">
              This will permanently delete all data. Enter your admin password to confirm.
            </p>
            <div className="mb-4">
              <label className="label">Admin Password</label>
              <input
                type="password"
                value={resetPassword}
                onChange={(e) => setResetPassword(e.target.value)}
                className="input"
                placeholder="Enter admin password"
              />
            </div>
            {resetCountdown > 0 && (
              <p className="text-sm text-amber-600 mb-4">
                Please wait {resetCountdown} seconds before confirming...
              </p>
            )}
            <div className="flex justify-end gap-3">
              <button onClick={() => setShowFactoryReset(false)} className="btn-secondary">
                Cancel
              </button>
              <button
                onClick={() => factoryResetMutation.mutate({ password: resetPassword })}
                disabled={resetCountdown > 0 || !resetPassword || factoryResetMutation.isPending}
                className="inline-flex items-center justify-center px-4 py-2 bg-red-600 text-white font-medium rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {factoryResetMutation.isPending ? (
                  <>
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                    Resetting...
                  </>
                ) : resetCountdown > 0 ? (
                  `Wait ${resetCountdown}s`
                ) : (
                  'Confirm Factory Reset'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
