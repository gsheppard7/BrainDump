import { NavLink, Outlet } from 'react-router-dom'

import { useMeta } from '../hooks'

const navClass = ({ isActive }: { isActive: boolean }) =>
  `rounded-md px-3 py-1.5 text-sm font-medium transition ${
    isActive ? 'bg-stone-900 text-white' : 'text-stone-600 hover:bg-stone-200/60 hover:text-stone-900'
  }`

export function Layout() {
  const meta = useMeta()
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-10 border-b border-stone-200 bg-stone-50/90 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-5xl items-center gap-6 px-4">
          <NavLink to="/" className="flex items-center gap-2 font-semibold tracking-tight">
            <img src="/favicon.svg" alt="" className="size-6" />
            BrainDump
          </NavLink>
          <nav className="flex gap-1">
            <NavLink to="/" end className={navClass}>
              Capture
            </NavLink>
            <NavLink to="/library" className={navClass}>
              Library
            </NavLink>
          </nav>
          <div className="ml-auto text-xs">
            {meta.isError ? (
              <span className="text-rose-700">API unreachable</span>
            ) : meta.data && !meta.data.database ? (
              <span className="text-rose-700">Database unavailable</span>
            ) : null}
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  )
}
