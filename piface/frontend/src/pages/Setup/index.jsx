import { useEffect } from 'react'
import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { ScanFace } from 'lucide-react'
import CompanyStep from './CompanyStep'
import HoursStep from './HoursStep'
import CalibrationStep from './CalibrationStep'
import CompleteStep from './CompleteStep'

const steps = [
  { path: 'company', label: 'Company', number: 1 },
  { path: 'hours', label: 'Hours', number: 2 },
  { path: 'calibration', label: 'Calibration', number: 3 },
  { path: 'complete', label: 'Complete', number: 4 },
]

function StepIndicator({ currentPath }) {
  const currentIndex = steps.findIndex((s) => currentPath.includes(s.path))

  return (
    <div className="flex items-center justify-center gap-1 sm:gap-2">
      {steps.map((step, index) => {
        const isActive = index === currentIndex
        const isComplete = index < currentIndex

        return (
          <div key={step.path} className="flex items-center">
            <div className="flex items-center gap-1.5">
              <div
                className={`w-7 h-7 sm:w-8 sm:h-8 rounded-full flex items-center justify-center text-xs sm:text-sm font-semibold transition-colors ${
                  isActive
                    ? 'bg-primary-600 text-white'
                    : isComplete
                    ? 'bg-primary-100 text-primary-700'
                    : 'bg-gray-200 text-gray-500'
                }`}
              >
                {isComplete ? '\u2713' : step.number}
              </div>
              <span
                className={`hidden sm:inline text-sm font-medium ${
                  isActive ? 'text-primary-700' : isComplete ? 'text-primary-600' : 'text-gray-400'
                }`}
              >
                {step.label}
              </span>
            </div>
            {index < steps.length - 1 && (
              <div
                className={`w-6 sm:w-12 h-0.5 mx-1 sm:mx-2 ${
                  index < currentIndex ? 'bg-primary-400' : 'bg-gray-200'
                }`}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}

export default function Setup() {
  const location = useLocation()

  // Warn before leaving during setup (steps 1-3)
  useEffect(() => {
    const isComplete = location.pathname.includes('complete')
    if (isComplete) return

    function handleBeforeUnload(e) {
      e.preventDefault()
      e.returnValue = ''
    }

    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [location.pathname])

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-4 py-4">
        <div className="max-w-2xl mx-auto flex flex-col items-center gap-4">
          <div className="flex items-center gap-2">
            <ScanFace className="w-7 h-7 text-primary-600" />
            <span className="text-lg font-bold text-gray-900">PiFace Setup</span>
          </div>
          <StepIndicator currentPath={location.pathname} />
        </div>
      </header>

      {/* Step content */}
      <div className="flex-1 flex items-start justify-center px-4 py-6 sm:py-10">
        <div className="w-full max-w-2xl">
          <Routes>
            <Route path="company" element={<CompanyStep />} />
            <Route path="hours" element={<HoursStep />} />
            <Route path="calibration" element={<CalibrationStep />} />
            <Route path="complete" element={<CompleteStep />} />
            <Route path="*" element={<Navigate to="company" replace />} />
          </Routes>
        </div>
      </div>
    </div>
  )
}
