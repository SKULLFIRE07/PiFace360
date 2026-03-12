import React, { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import {
  Camera,
  RefreshCw,
  CheckCircle2,
  XCircle,
  LogIn,
  LogOut,
  Monitor,
  Save,
  Loader2,
} from 'lucide-react'

function CameraCard({ cam, inDevice, outDevice, onAssign }) {
  const isIn = cam.device_index === inDevice
  const isOut = cam.device_index === outDevice

  return (
    <div
      className={`card border-2 transition-all ${
        isIn
          ? 'border-green-400 bg-green-50/50'
          : isOut
          ? 'border-blue-400 bg-blue-50/50'
          : 'border-gray-200'
      }`}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div
            className={`p-2.5 rounded-lg ${
              isIn
                ? 'bg-green-100 text-green-600'
                : isOut
                ? 'bg-blue-100 text-blue-600'
                : 'bg-gray-100 text-gray-500'
            }`}
          >
            <Camera className="w-6 h-6" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-gray-900">
              Camera {cam.device_index}
            </h3>
            <p className="text-xs text-gray-500">
              /dev/video{cam.device_index}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {cam.working ? (
            <span className="flex items-center gap-1 text-xs text-green-600 bg-green-100 px-2 py-0.5 rounded-full">
              <CheckCircle2 className="w-3 h-3" /> Working
            </span>
          ) : (
            <span className="flex items-center gap-1 text-xs text-red-500 bg-red-100 px-2 py-0.5 rounded-full">
              <XCircle className="w-3 h-3" /> No Signal
            </span>
          )}
        </div>
      </div>

      {/* Camera info */}
      <div className="flex items-center gap-4 text-xs text-gray-500 mb-4">
        <span className="flex items-center gap-1">
          <Monitor className="w-3 h-3" />
          {cam.resolution}
        </span>
        {cam.fps > 0 && <span>{cam.fps} fps</span>}
      </div>

      {/* Current role badge */}
      {(isIn || isOut) && (
        <div className="mb-3">
          <span
            className={`inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-full ${
              isIn
                ? 'bg-green-200 text-green-800'
                : 'bg-blue-200 text-blue-800'
            }`}
          >
            {isIn ? <LogIn className="w-3.5 h-3.5" /> : <LogOut className="w-3.5 h-3.5" />}
            Assigned as {isIn ? 'ENTRANCE (IN)' : 'EXIT (OUT)'} Camera
          </span>
        </div>
      )}

      {/* Assign buttons */}
      <div className="flex gap-2">
        <button
          onClick={() => onAssign('in', cam.device_index)}
          disabled={isIn}
          className={`flex-1 text-xs py-2 px-3 rounded-lg font-medium flex items-center justify-center gap-1.5 transition-colors ${
            isIn
              ? 'bg-green-200 text-green-800 cursor-default'
              : 'bg-white border border-green-300 text-green-700 hover:bg-green-50'
          }`}
        >
          <LogIn className="w-3.5 h-3.5" />
          {isIn ? 'IN Camera' : 'Set as IN'}
        </button>
        <button
          onClick={() => onAssign('out', cam.device_index)}
          disabled={isOut}
          className={`flex-1 text-xs py-2 px-3 rounded-lg font-medium flex items-center justify-center gap-1.5 transition-colors ${
            isOut
              ? 'bg-blue-200 text-blue-800 cursor-default'
              : 'bg-white border border-blue-300 text-blue-700 hover:bg-blue-50'
          }`}
        >
          <LogOut className="w-3.5 h-3.5" />
          {isOut ? 'OUT Camera' : 'Set as OUT'}
        </button>
      </div>
    </div>
  )
}

export default function Cameras() {
  const queryClient = useQueryClient()
  const [scanning, setScanning] = useState(false)

  // Fetch detected cameras
  const {
    data: detectData,
    isLoading: detectLoading,
    refetch: rescan,
  } = useQuery({
    queryKey: ['cameras', 'detect'],
    queryFn: () => api.get('/stream/cameras/detect').then((r) => r.data),
  })

  // Fetch current assignments
  const { data: assignData } = useQuery({
    queryKey: ['cameras', 'assignments'],
    queryFn: () => api.get('/stream/cameras').then((r) => r.data),
  })

  // Assign mutation
  const assignMutation = useMutation({
    mutationFn: (body) => api.post('/stream/cameras/assign', body).then((r) => r.data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cameras'] })
    },
  })

  const cameras = detectData?.cameras || []
  const inDevice = assignData?.in_device ?? 0
  const outDevice = assignData?.out_device ?? 2

  const handleRescan = useCallback(async () => {
    setScanning(true)
    await rescan()
    setScanning(false)
  }, [rescan])

  const handleAssign = useCallback(
    (role, deviceIndex) => {
      assignMutation.mutate({ [role]: deviceIndex })
    },
    [assignMutation]
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-gray-900">Camera Setup</h1>
          <p className="text-sm text-gray-500 mt-1">
            Detect connected cameras and assign them as Entrance (IN) or Exit (OUT)
          </p>
        </div>
        <button
          onClick={handleRescan}
          disabled={scanning || detectLoading}
          className="btn-primary flex items-center gap-2"
        >
          {scanning || detectLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <RefreshCw className="w-4 h-4" />
          )}
          {scanning ? 'Scanning...' : 'Scan for Cameras'}
        </button>
      </div>

      {/* Current assignment summary */}
      <div className="card bg-gray-50">
        <h2 className="text-sm font-semibold text-gray-700 mb-3">Current Assignment</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="flex items-center gap-3 bg-white rounded-lg p-3 border border-green-200">
            <div className="p-2 bg-green-100 rounded-lg">
              <LogIn className="w-5 h-5 text-green-600" />
            </div>
            <div>
              <p className="text-xs text-gray-500 font-medium">Entrance (IN)</p>
              <p className="text-sm font-bold text-gray-900">
                Camera {inDevice}
                <span className="text-xs font-normal text-gray-400 ml-1">
                  /dev/video{inDevice}
                </span>
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3 bg-white rounded-lg p-3 border border-blue-200">
            <div className="p-2 bg-blue-100 rounded-lg">
              <LogOut className="w-5 h-5 text-blue-600" />
            </div>
            <div>
              <p className="text-xs text-gray-500 font-medium">Exit (OUT)</p>
              <p className="text-sm font-bold text-gray-900">
                Camera {outDevice}
                <span className="text-xs font-normal text-gray-400 ml-1">
                  /dev/video{outDevice}
                </span>
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Detected cameras grid */}
      {detectLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="card animate-pulse">
              <div className="h-6 bg-gray-200 rounded w-32 mb-3" />
              <div className="h-4 bg-gray-200 rounded w-24 mb-4" />
              <div className="h-8 bg-gray-200 rounded w-full" />
            </div>
          ))}
        </div>
      ) : cameras.length === 0 ? (
        <div className="card text-center py-12">
          <Camera className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <h3 className="text-lg font-semibold text-gray-600">No cameras detected</h3>
          <p className="text-sm text-gray-500 mt-1">
            Connect a USB camera and click "Scan for Cameras"
          </p>
        </div>
      ) : (
        <>
          <h2 className="text-sm font-semibold text-gray-600">
            {cameras.length} camera{cameras.length !== 1 ? 's' : ''} detected
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {cameras.map((cam) => (
              <CameraCard
                key={cam.device_index}
                cam={cam}
                inDevice={inDevice}
                outDevice={outDevice}
                onAssign={handleAssign}
              />
            ))}
          </div>
        </>
      )}

      {/* Save confirmation */}
      {assignMutation.isSuccess && (
        <div className="flex items-center gap-2 text-sm text-green-600 bg-green-50 border border-green-200 rounded-lg px-4 py-3">
          <CheckCircle2 className="w-4 h-4" />
          Camera assignments saved successfully!
        </div>
      )}
      {assignMutation.isError && (
        <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
          <XCircle className="w-4 h-4" />
          Failed to save assignments. Please try again.
        </div>
      )}

      {/* Info box */}
      <div className="card bg-amber-50 border border-amber-200">
        <h3 className="text-sm font-semibold text-amber-800 mb-2">How it works</h3>
        <ul className="text-xs text-amber-700 space-y-1.5 list-disc list-inside">
          <li>The <strong>IN camera</strong> is placed at the entrance — it detects people arriving</li>
          <li>The <strong>OUT camera</strong> is placed at the exit — it detects people leaving</li>
          <li>On Raspberry Pi 5, connect USB cameras and scan to detect them</li>
          <li>Camera assignments are saved and persist across restarts</li>
          <li>Both cameras run simultaneously for real-time attendance tracking</li>
        </ul>
      </div>
    </div>
  )
}
