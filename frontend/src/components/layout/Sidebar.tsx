import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Package,
  Tags,
  Store as StoreIcon,
  ListChecks,
  UserRound,
  LogOut,
  Menu,
  X,
  ChevronLeft,
} from 'lucide-react'
import logo from '@/assets/logo.png'
import { cn } from '@/utils/cn'
import { useAuth } from '@/hooks/useAuth'

const nav = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/products', label: 'Products', icon: Package },
  { to: '/categories', label: 'Categories', icon: Tags },
  { to: '/stores', label: 'Stores', icon: StoreIcon },
  { to: '/attributes', label: 'Product Attributes', icon: ListChecks },
]

export function Sidebar({
  collapsed,
  mobileOpen,
  onToggleCollapse,
  onCloseMobile,
}: {
  collapsed: boolean
  mobileOpen: boolean
  onToggleCollapse: () => void
  onCloseMobile: () => void
}) {
  const { user, signOut } = useAuth()

  const content = (
    <div className="flex h-full flex-col bg-white">
      <div className={cn('flex h-20 items-center border-b border-line px-4', collapsed && 'justify-center px-2')}>
        <img src={logo} alt="MY Trolley" className={cn('h-11 w-auto', collapsed && 'h-9')} />
      </div>

      <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-5">
        <div>
          <p className={cn('mb-2 px-3 text-[10px] font-semibold uppercase tracking-widest text-subtle', collapsed && 'text-center')}>
            {!collapsed && 'Workspace'}
          </p>
          <div className="space-y-1">
            {nav.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={onCloseMobile}
                title={item.label}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 rounded-control px-3 py-2.5 text-sm font-medium transition-colors',
                    collapsed && 'justify-center px-0',
                    isActive
                      ? 'bg-forest text-white shadow-card'
                      : 'text-subtle hover:bg-lime-soft hover:text-forest',
                  )
                }
              >
                <item.icon className="h-[18px] w-[18px] shrink-0" />
                {!collapsed && <span>{item.label}</span>}
              </NavLink>
            ))}
          </div>
        </div>
        <div>
          <p className={cn('mb-2 px-3 text-[10px] font-semibold uppercase tracking-widest text-subtle', collapsed && 'text-center')}>
            {!collapsed && 'Account'}
          </p>
          <NavLink
            to="/account"
            onClick={onCloseMobile}
            title="My Account"
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-control px-3 py-2.5 text-sm font-medium transition-colors',
                collapsed && 'justify-center px-0',
                isActive
                  ? 'bg-forest text-white shadow-card'
                  : 'text-subtle hover:bg-lime-soft hover:text-forest',
              )
            }
          >
            <UserRound className="h-[18px] w-[18px] shrink-0" />
            {!collapsed && <span>My Account</span>}
          </NavLink>
          <button
            onClick={() => void signOut()}
            title="Logout"
            className={cn(
              'flex w-full items-center gap-3 rounded-control px-3 py-2.5 text-sm font-medium text-subtle transition-colors hover:bg-danger/10 hover:text-danger',
              collapsed && 'justify-center px-0',
            )}
          >
            <LogOut className="h-[18px] w-[18px] shrink-0" />
            {!collapsed && <span>Logout</span>}
          </button>
        </div>
      </nav>

      {!collapsed && (
        <div className="border-t border-line px-4 py-4">
          <p className="truncate text-sm font-semibold text-ink">
            {user?.full_name || user?.username || 'Admin user'}
          </p>
          <p className="truncate text-xs text-subtle">{user?.roles?.join(', ') || 'Administrator'}</p>
        </div>
      )}
    </div>
  )

  return (
    <>
      <aside
        className={cn(
          'hidden shrink-0 border-r border-line lg:block',
          collapsed ? 'w-[76px]' : 'w-[248px]',
        )}
      >
        <div className="sticky top-0 h-screen">{content}</div>
      </aside>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            aria-label="Close navigation"
            className="absolute inset-0 bg-forest-deep/40"
            onClick={onCloseMobile}
          />
          <div className="relative h-full w-[264px] shadow-float">
            <button
              aria-label="Close navigation"
              onClick={onCloseMobile}
              className="absolute right-3 top-5 z-10 rounded-control p-1 text-subtle hover:bg-muted"
            >
              <X className="h-5 w-5" />
            </button>
            {content}
          </div>
        </div>
      )}

      {/* Collapse toggle (desktop) */}
      <button
        onClick={onToggleCollapse}
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        className="fixed bottom-4 left-[252px] z-30 hidden h-8 w-8 items-center justify-center rounded-full border border-line bg-white text-subtle shadow-card transition-all lg:flex [body:has(aside)+div_&]:left-auto"
        style={{ left: collapsed ? 88 : 260 }}
      >
        {collapsed ? <Menu className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
      </button>
    </>
  )
}
