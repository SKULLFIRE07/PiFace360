import Sidebar from './Sidebar'
import BottomNav from './BottomNav'
import ConnectionBanner from '../ConnectionBanner'

export default function AppShell({ children }) {
  return (
    <div className="flex min-h-screen">
      <Sidebar />

      <div className="flex-1 flex flex-col min-w-0">
        <ConnectionBanner />

        <main className="flex-1 p-4 sm:p-6 lg:p-8 pb-20 lg:pb-8 overflow-y-auto">
          {children}
        </main>
      </div>

      <BottomNav />
    </div>
  )
}
