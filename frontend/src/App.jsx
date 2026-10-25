import { Link, NavLink, Route, Routes } from 'react-router-dom'
import { USE_MOCK } from './api'
import MainScreen from './pages/MainScreen'
import Simulator from './pages/Simulator'

function NavItem({ to, children }) {
  return (
    <NavLink
      to={to}
      end
      className={({ isActive }) =>
        `rounded-md px-3 py-1.5 text-sm ${isActive ? 'bg-accent-50 text-accent-700' : 'text-gray-600 hover:text-gray-900'}`
      }
    >
      {children}
    </NavLink>
  )
}

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50 text-gray-800">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2 px-4 py-3">
          <h1>
            <Link to="/" className="flex items-center gap-2 font-semibold text-gray-900 hover:text-accent-700">
              <span className="inline-block h-2.5 w-2.5 rounded-full bg-accent-500" /> PowerCheck
              <span className="hidden text-xs font-normal text-gray-400 sm:inline">AI Outage Concierge</span>
            </Link>
          </h1>
          <nav className="flex gap-1">
            <NavItem to="/">My home</NavItem>
            <NavItem to="/simulator">Storm simulator</NavItem>
          </nav>
        </div>
      </header>
      {USE_MOCK && (
        <p className="border-b border-amber-100 bg-amber-50 px-4 py-1 text-center text-xs text-amber-700">
          Demo data: not connected to the backend yet.
        </p>
      )}
      <main className="mx-auto max-w-7xl p-4">
        <Routes>
          <Route path="/" element={<MainScreen />} />
          <Route path="/simulator" element={<Simulator />} />
        </Routes>
      </main>
    </div>
  )
}
