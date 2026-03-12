import { useState, useRef, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Video, Undo2, Redo2, Loader2, Trash2 } from 'lucide-react'
import { api } from '../../api/client'

const CANVAS_W = 640
const CANVAS_H = 480

export default function CalibrationStep() {
  const navigate = useNavigate()
  const canvasRef = useRef(null)
  const containerRef = useRef(null)

  const [inArrow, setInArrow] = useState(null) // { x1, y1, x2, y2 }
  const [outArrow, setOutArrow] = useState(null)
  const [drawingMode, setDrawingMode] = useState('in') // 'in' | 'out'
  const [currentDraw, setCurrentDraw] = useState(null) // { x1, y1, x2, y2 }
  const [isDrawing, setIsDrawing] = useState(false)
  const [history, setHistory] = useState([])
  const [historyIndex, setHistoryIndex] = useState(-1)
  const [loading, setLoading] = useState(false)
  const [apiError, setApiError] = useState('')

  // Convert screen coords to normalized 640x480
  const normalizeCoords = useCallback((clientX, clientY) => {
    const container = containerRef.current
    if (!container) return { x: 0, y: 0 }
    const rect = container.getBoundingClientRect()
    const scaleX = CANVAS_W / rect.width
    const scaleY = CANVAS_H / rect.height
    return {
      x: Math.round((clientX - rect.left) * scaleX),
      y: Math.round((clientY - rect.top) * scaleY),
    }
  }, [])

  function handlePointerDown(e) {
    e.preventDefault()
    const { x, y } = normalizeCoords(e.clientX, e.clientY)
    setIsDrawing(true)
    setCurrentDraw({ x1: x, y1: y, x2: x, y2: y })
    e.target.setPointerCapture(e.pointerId)
  }

  function handlePointerMove(e) {
    if (!isDrawing || !currentDraw) return
    e.preventDefault()
    const { x, y } = normalizeCoords(e.clientX, e.clientY)
    setCurrentDraw((prev) => ({ ...prev, x2: x, y2: y }))
  }

  function handlePointerUp(e) {
    if (!isDrawing || !currentDraw) return
    e.preventDefault()
    setIsDrawing(false)

    const { x1, y1, x2, y2 } = currentDraw
    const dist = Math.sqrt(Math.pow(x2 - x1, 2) + Math.pow(y2 - y1, 2))
    if (dist < 10) {
      setCurrentDraw(null)
      return
    }

    const arrow = { x1, y1, x2, y2 }
    if (drawingMode === 'in') {
      setInArrow(arrow)
    } else {
      setOutArrow(arrow)
    }

    // Push to history
    const newEntry = {
      inArrow: drawingMode === 'in' ? arrow : inArrow,
      outArrow: drawingMode === 'out' ? arrow : outArrow,
    }
    const newHistory = history.slice(0, historyIndex + 1)
    newHistory.push(newEntry)
    setHistory(newHistory)
    setHistoryIndex(newHistory.length - 1)

    setCurrentDraw(null)
  }

  function undo() {
    if (historyIndex <= 0) {
      setInArrow(null)
      setOutArrow(null)
      setHistoryIndex(-1)
      return
    }
    const prev = history[historyIndex - 1]
    setInArrow(prev.inArrow)
    setOutArrow(prev.outArrow)
    setHistoryIndex(historyIndex - 1)
  }

  function redo() {
    if (historyIndex >= history.length - 1) return
    const next = history[historyIndex + 1]
    setInArrow(next.inArrow)
    setOutArrow(next.outArrow)
    setHistoryIndex(historyIndex + 1)
  }

  // Draw canvas overlay
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, CANVAS_W, CANVAS_H)

    function drawArrow(arrow, color, label) {
      if (!arrow) return
      const { x1, y1, x2, y2 } = arrow
      const angle = Math.atan2(y2 - y1, x2 - x1)
      const headLen = 16

      ctx.beginPath()
      ctx.moveTo(x1, y1)
      ctx.lineTo(x2, y2)
      ctx.strokeStyle = color
      ctx.lineWidth = 3
      ctx.stroke()

      // Arrowhead
      ctx.beginPath()
      ctx.moveTo(x2, y2)
      ctx.lineTo(
        x2 - headLen * Math.cos(angle - Math.PI / 6),
        y2 - headLen * Math.sin(angle - Math.PI / 6)
      )
      ctx.lineTo(
        x2 - headLen * Math.cos(angle + Math.PI / 6),
        y2 - headLen * Math.sin(angle + Math.PI / 6)
      )
      ctx.closePath()
      ctx.fillStyle = color
      ctx.fill()

      // Label
      const midX = (x1 + x2) / 2
      const midY = (y1 + y2) / 2
      ctx.font = 'bold 14px sans-serif'
      ctx.fillStyle = color
      ctx.textAlign = 'center'
      ctx.fillText(label, midX, midY - 10)
    }

    drawArrow(inArrow, '#22c55e', 'IN')
    drawArrow(outArrow, '#ef4444', 'OUT')

    // Current drawing
    if (currentDraw && isDrawing) {
      const color = drawingMode === 'in' ? '#22c55e' : '#ef4444'
      const label = drawingMode === 'in' ? 'IN' : 'OUT'
      drawArrow(currentDraw, color + '80', label)
    }
  }, [inArrow, outArrow, currentDraw, isDrawing, drawingMode])

  async function handleNext(e) {
    e.preventDefault()
    if (!inArrow || !outArrow) {
      setApiError('Please draw both IN and OUT direction arrows.')
      return
    }

    setLoading(true)
    setApiError('')
    try {
      await api.post('/calibration/set', {
        in_vector: { x1: inArrow.x1, y1: inArrow.y1, x2: inArrow.x2, y2: inArrow.y2 },
        out_vector: { x1: outArrow.x1, y1: outArrow.y1, x2: outArrow.x2, y2: outArrow.y2 },
      })
      navigate('/setup/complete')
    } catch (err) {
      setApiError(err.response?.data?.detail || 'Failed to save calibration.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 bg-primary-100 rounded-lg flex items-center justify-center">
          <Video className="w-5 h-5 text-primary-600" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Direction Calibration</h2>
          <p className="text-sm text-gray-500">Draw arrows to define IN and OUT directions</p>
        </div>
      </div>

      {apiError && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {apiError}
        </div>
      )}

      {/* Instructions */}
      <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800">
        <p className="font-medium mb-1">How to calibrate:</p>
        <ol className="list-decimal list-inside space-y-1 text-blue-700">
          <li>Select "IN Direction" and draw an arrow showing how people walk <strong>into</strong> the building.</li>
          <li>Select "OUT Direction" and draw an arrow showing how people walk <strong>out of</strong> the building.</li>
          <li>Click and drag on the video feed to draw each arrow.</li>
        </ol>
      </div>

      {/* Mode selector */}
      <div className="flex gap-2 mb-3">
        <button
          type="button"
          onClick={() => setDrawingMode('in')}
          className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
            drawingMode === 'in'
              ? 'bg-green-100 border-green-400 text-green-800'
              : 'bg-white border-gray-300 text-gray-600 hover:bg-gray-50'
          }`}
        >
          IN Direction
        </button>
        <button
          type="button"
          onClick={() => setDrawingMode('out')}
          className={`px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
            drawingMode === 'out'
              ? 'bg-red-100 border-red-400 text-red-800'
              : 'bg-white border-gray-300 text-gray-600 hover:bg-gray-50'
          }`}
        >
          OUT Direction
        </button>
      </div>

      {/* Video + Canvas overlay */}
      <div
        ref={containerRef}
        className="relative w-full aspect-[4/3] bg-gray-900 rounded-lg overflow-hidden select-none"
        style={{ touchAction: 'none' }}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
      >
        <img
          src="/api/stream/video"
          alt="Live camera feed"
          className="absolute inset-0 w-full h-full object-contain pointer-events-none"
          draggable={false}
        />
        <canvas
          ref={canvasRef}
          width={CANVAS_W}
          height={CANVAS_H}
          className="absolute inset-0 w-full h-full pointer-events-none"
        />
      </div>

      {/* Controls */}
      <div className="flex items-center gap-2 mt-3">
        <button
          type="button"
          onClick={undo}
          disabled={historyIndex < 0}
          className="btn-secondary text-sm px-3 py-1.5"
          title="Undo"
        >
          <Undo2 className="w-4 h-4" />
        </button>
        <button
          type="button"
          onClick={redo}
          disabled={historyIndex >= history.length - 1}
          className="btn-secondary text-sm px-3 py-1.5"
          title="Redo"
        >
          <Redo2 className="w-4 h-4" />
        </button>
        <button
          type="button"
          onClick={() => {
            setInArrow(null)
            setOutArrow(null)
            setHistory([])
            setHistoryIndex(-1)
          }}
          className="btn-secondary text-sm px-3 py-1.5 text-red-600 hover:text-red-700"
          title="Clear all"
        >
          <Trash2 className="w-4 h-4" />
        </button>

        {/* Status indicators */}
        <div className="ml-auto flex items-center gap-3 text-xs">
          <span className={inArrow ? 'text-green-600 font-medium' : 'text-gray-400'}>
            IN {inArrow ? '\u2713' : '\u2717'}
          </span>
          <span className={outArrow ? 'text-red-600 font-medium' : 'text-gray-400'}>
            OUT {outArrow ? '\u2713' : '\u2717'}
          </span>
        </div>
      </div>

      {/* Navigation */}
      <div className="flex justify-between pt-6">
        <button
          type="button"
          onClick={() => navigate('/setup/hours')}
          className="btn-secondary"
          disabled={loading}
        >
          Back
        </button>
        <button onClick={handleNext} className="btn-primary" disabled={loading}>
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
    </div>
  )
}
