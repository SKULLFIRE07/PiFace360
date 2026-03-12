import React, { useState, useEffect, useRef, useCallback } from 'react'
import { Video, VideoOff, Camera, Wifi, WifiOff, LogIn, LogOut } from 'lucide-react'

const AUTO_OFF_MINUTES = 5

function CameraPanel({ label, icon: Icon, camera, feedOpen, onImgError, onImgLoad }) {
  if (!feedOpen) return null
  return (
    <div className="flex-1 min-w-0">
      <div className="flex items-center gap-1.5 mb-1.5">
        <Icon className="w-3.5 h-3.5" />
        <span className="text-xs font-semibold text-gray-600">{label}</span>
      </div>
      <div className="relative rounded-lg overflow-hidden bg-black aspect-video">
        <img
          src={`/api/stream/video?camera=${camera}`}
          alt={`${label} camera feed`}
          className="w-full h-full object-contain"
          onError={onImgError}
          onLoad={onImgLoad}
        />
      </div>
    </div>
  )
}

export default function LiveFeed({ className = '' }) {
  const [feedOpen, setFeedOpen] = useState(false)
  const [snapshotUrl, setSnapshotUrl] = useState(null)
  const [snapshotCamera, setSnapshotCamera] = useState(null)
  const [showPrompt, setShowPrompt] = useState(false)
  const [connectedIn, setConnectedIn] = useState(true)
  const [connectedOut, setConnectedOut] = useState(true)
  const timerRef = useRef(null)

  const resetTimer = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current)
    setShowPrompt(false)
    timerRef.current = setTimeout(() => {
      setShowPrompt(true)
    }, AUTO_OFF_MINUTES * 60 * 1000)
  }, [])

  const openFeed = useCallback(() => {
    setFeedOpen(true)
    setSnapshotUrl(null)
    setSnapshotCamera(null)
    setShowPrompt(false)
    resetTimer()
  }, [resetTimer])

  const closeFeed = useCallback(() => {
    setFeedOpen(false)
    setShowPrompt(false)
    if (timerRef.current) clearTimeout(timerRef.current)
  }, [])

  const continueWatching = useCallback(() => {
    setShowPrompt(false)
    resetTimer()
  }, [resetTimer])

  const stopWatching = useCallback(() => {
    closeFeed()
  }, [closeFeed])

  const loadSnapshot = useCallback((cam = 'in') => {
    setFeedOpen(false)
    setSnapshotUrl(`/api/stream/snapshot?camera=${cam}&t=${Date.now()}`)
    setSnapshotCamera(cam)
    if (timerRef.current) clearTimeout(timerRef.current)
  }, [])

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [])

  const connected = connectedIn || connectedOut

  return (
    <div className={`card ${className}`}>
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
          <Video className="w-4 h-4" />
          Dual Camera Feed
        </h3>
        <div className="flex items-center gap-2 flex-wrap">
          <span
            className={`flex items-center gap-1 text-xs ${
              connected ? 'text-green-600' : 'text-red-500'
            }`}
          >
            {connected ? (
              <Wifi className="w-3 h-3" />
            ) : (
              <WifiOff className="w-3 h-3" />
            )}
            {connected ? 'Connected' : 'Disconnected'}
          </span>
          {!feedOpen ? (
            <button onClick={openFeed} className="btn-primary text-xs px-3 py-1">
              <Video className="w-3.5 h-3.5 mr-1" />
              View Live Feed
            </button>
          ) : (
            <button onClick={closeFeed} className="btn-secondary text-xs px-3 py-1">
              <VideoOff className="w-3.5 h-3.5 mr-1" />
              Stop Feed
            </button>
          )}
          <button onClick={() => loadSnapshot('in')} className="btn-secondary text-xs px-3 py-1">
            <Camera className="w-3.5 h-3.5 mr-1" />
            Snap IN
          </button>
          <button onClick={() => loadSnapshot('out')} className="btn-secondary text-xs px-3 py-1">
            <Camera className="w-3.5 h-3.5 mr-1" />
            Snap OUT
          </button>
        </div>
      </div>

      {/* Dual camera feeds side by side */}
      {feedOpen && !showPrompt && (
        <div className="flex gap-3">
          <CameraPanel
            label="Entrance (IN)"
            icon={LogIn}
            camera="in"
            feedOpen={feedOpen}
            onImgError={() => setConnectedIn(false)}
            onImgLoad={() => setConnectedIn(true)}
          />
          <CameraPanel
            label="Exit (OUT)"
            icon={LogOut}
            camera="out"
            feedOpen={feedOpen}
            onImgError={() => setConnectedOut(false)}
            onImgLoad={() => setConnectedOut(true)}
          />
        </div>
      )}

      {/* Still watching prompt */}
      {feedOpen && showPrompt && (
        <div className="rounded-lg bg-gray-900 aspect-video flex flex-col items-center justify-center gap-4 text-white">
          <p className="text-lg font-medium">Still watching?</p>
          <p className="text-sm text-gray-400">
            The feed has been running for {AUTO_OFF_MINUTES} minutes.
          </p>
          <div className="flex gap-3">
            <button onClick={continueWatching} className="btn-primary text-sm">
              Continue Watching
            </button>
            <button onClick={stopWatching} className="btn-secondary text-sm">
              Stop Feed
            </button>
          </div>
        </div>
      )}

      {/* Snapshot display */}
      {snapshotUrl && !feedOpen && (
        <div>
          <div className="flex items-center gap-1.5 mb-1.5">
            {snapshotCamera === 'out' ? (
              <LogOut className="w-3.5 h-3.5 text-gray-600" />
            ) : (
              <LogIn className="w-3.5 h-3.5 text-gray-600" />
            )}
            <span className="text-xs font-semibold text-gray-600">
              {snapshotCamera === 'out' ? 'Exit (OUT)' : 'Entrance (IN)'} Snapshot
            </span>
          </div>
          <div className="relative rounded-lg overflow-hidden bg-black aspect-video">
            <img
              src={snapshotUrl}
              alt="Camera snapshot"
              className="w-full h-full object-contain"
              onError={() => { setConnectedIn(false); setConnectedOut(false) }}
              onLoad={() => { setConnectedIn(true); setConnectedOut(true) }}
            />
          </div>
        </div>
      )}

      {/* Placeholder when nothing active */}
      {!feedOpen && !snapshotUrl && (
        <div className="rounded-lg bg-gray-100 aspect-video flex flex-col items-center justify-center gap-2">
          <div className="flex items-center gap-4 text-gray-400">
            <div className="flex items-center gap-1">
              <LogIn className="w-4 h-4" />
              <span className="text-xs">IN</span>
            </div>
            <span className="text-gray-300">|</span>
            <div className="flex items-center gap-1">
              <LogOut className="w-4 h-4" />
              <span className="text-xs">OUT</span>
            </div>
          </div>
          <p className="text-sm text-gray-500">Click "View Live Feed" to start dual camera streaming</p>
        </div>
      )}
    </div>
  )
}
