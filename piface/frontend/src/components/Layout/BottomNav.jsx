import { useState, useRef, useEffect } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  Home,
  Users,
  BarChart3,
  Calendar,
  MoreHorizontal,
  UserX,
  ClipboardList,
  Camera,
  Settings,
} from 'lucide-react'

const primaryTabs = [
  { to: '/today', label: 'Today', icon: Home },
  { to: '/employees', label: 'Employees', icon: Users },
  { to: '/reports', label: 'Reports', icon: BarChart3 },
  { to: '/leave', label: 'Leave', icon: Calendar },
]

const moreItems = [
  { to: '/unknowns', label: 'Unknowns', icon: UserX },
  { to: '/attendance', label: 'Attendance', icon: ClipboardList },
  { to: '/cameras', label: 'Cameras', icon: Camera },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export default function BottomNav() {
  const [showMore, setShowMore] = useState(false)
  const moreRef = useRef(null)
  const navigate = useNavigate()

  // Close popup on outside click
  useEffect(() => {
    function handleClickOutside(e) {
      if (moreRef.current && !moreRef.current.contains(e.target)) {
        setShowMore(false)
      }
    }

    if (showMore) {
      document.addEventListener('pointerdown', handleClickOutside)
    }
    return () => document.removeEventListener('pointerdown', handleClickOutside)
  }, [showMore])

  return (
    <nav className="lg:hidden fixed bottom-0 inset-x-0 bg-white border-t border-gray-200 z-50 safe-area-bottom">
      <div className="flex items-center justify-around h-16">
        {primaryTabs.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex flex-col items-center justify-center gap-0.5 px-2 py-1 min-w-0 flex-1 ${
                isActive ? 'text-primary-600' : 'text-gray-500'
              }`
            }
          >
            <Icon className="w-5 h-5" />
            <span className="text-[10px] font-medium truncate">{label}</span>
          </NavLink>
        ))}

        {/* More tab */}
        <div ref={moreRef} className="relative flex-1">
          <button
            onClick={() => setShowMore(!showMore)}
            className={`flex flex-col items-center justify-center gap-0.5 px-2 py-1 w-full ${
              showMore ? 'text-primary-600' : 'text-gray-500'
            }`}
          >
            <MoreHorizontal className="w-5 h-5" />
            <span className="text-[10px] font-medium">More</span>
          </button>

          {showMore && (
            <div className="absolute bottom-full right-0 mb-2 mr-2 w-48 bg-white rounded-xl shadow-lg border border-gray-200 py-1 z-50">
              {moreItems.map(({ to, label, icon: Icon }) => (
                <button
                  key={to}
                  onClick={() => {
                    setShowMore(false)
                    navigate(to)
                  }}
                  className="flex items-center gap-3 px-4 py-3 w-full text-left text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  <Icon className="w-5 h-5 text-gray-400" />
                  <span>{label}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </nav>
  )
}
