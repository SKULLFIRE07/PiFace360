import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Users,
  UserX,
  ClipboardList,
  BarChart3,
  Calendar,
  Camera,
  Settings,
  LogOut,
  ChevronLeft,
  ChevronRight,
  ScanFace,
} from 'lucide-react'
import { useAuth } from '../../hooks/useAuth'

const navItems = [
  { to: '/today', label: 'Today', icon: LayoutDashboard },
  { to: '/attendance', label: 'Attendance', icon: ClipboardList },
  { to: '/employees', label: 'Employees', icon: Users },
  { to: '/unknowns', label: 'Unknowns', icon: UserX },
  { to: '/reports', label: 'Reports', icon: BarChart3 },
  { to: '/leave', label: 'Leave', icon: Calendar },
  { to: '/cameras', label: 'Cameras', icon: Camera },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)
  const { logout } = useAuth()

  return (
    <aside
      className={`hidden lg:flex flex-col bg-white border-r border-gray-200 h-screen sticky top-0 transition-all duration-200 ${
        collapsed ? 'w-16' : 'w-60'
      }`}
    >
      {/* Logo */}
      <div className="flex items-center gap-3 px-4 h-16 border-b border-gray-200 shrink-0">
        <ScanFace className="w-8 h-8 text-primary-600 shrink-0" />
        {!collapsed && (
          <span className="text-lg font-bold text-gray-900 truncate">PiFace</span>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 overflow-y-auto">
        <ul className="space-y-1 px-2">
          {navItems.map(({ to, label, icon: Icon }) => (
            <li key={to}>
              <NavLink
                to={to}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors duration-150 ${
                    isActive
                      ? 'bg-primary-50 text-primary-700'
                      : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                  }`
                }
                title={collapsed ? label : undefined}
              >
                <Icon className="w-5 h-5 shrink-0" />
                {!collapsed && <span>{label}</span>}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      {/* Bottom actions */}
      <div className="border-t border-gray-200 p-2 space-y-1">
        <button
          onClick={logout}
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-gray-600 hover:bg-red-50 hover:text-red-600 w-full transition-colors duration-150"
          title={collapsed ? 'Logout' : undefined}
        >
          <LogOut className="w-5 h-5 shrink-0" />
          {!collapsed && <span>Logout</span>}
        </button>
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center justify-center w-full px-3 py-2 rounded-lg text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors duration-150"
        >
          {collapsed ? (
            <ChevronRight className="w-5 h-5" />
          ) : (
            <ChevronLeft className="w-5 h-5" />
          )}
        </button>
      </div>
    </aside>
  )
}
