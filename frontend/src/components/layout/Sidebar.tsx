import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Package,
  Tags,
  Store as StoreIcon,
  ListChecks,
  UserRound,
  LogOut,
  X,
  ChevronsLeft,
  ChevronsRight,
  Sun,
  Moon,
} from 'lucide-react'
import logo from '@/assets/mytrolley_logo_brand.png'
import { cn } from '@/utils/cn'
import { useAuth } from '@/hooks/useAuth'

const nav = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/products', label: 'Products', icon: Package },
  { to: '/categories', label: 'Categories', icon: Tags },
  { to: '/stores', label: 'Stores', icon: StoreIcon },
  { to: '/attributes', label: 'Product Attributes', icon: ListChecks },
]

const itemClass =
  'relative flex items-center gap-[14px] rounded-[13px] border border-transparent px-4 text-[15px] font-medium transition-colors'
const inactiveClass = 'text-[var(--text-2)] hover:bg-[var(--glass-bg)] hover:text-[var(--text-1)]'
const activeClass =
  'border-[rgba(52,211,153,.22)] text-[var(--text-1)] bg-[linear-gradient(90deg,rgba(47,191,139,.24),rgba(47,191,139,.05))] shadow-[0_0_28px_rgba(47,191,139,.14)]'

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p
      className="uppercase text-[11px] font-medium tracking-[.09em] text-[var(--text-3)]"
      style={{ padding: '0 14px', margin: '6px 0 var(--label-mb)' }}
    >
      {children}
    </p>
  )
}

function SegmentedToggle() {
  return (
    <div
      className="mb-4 flex rounded-[12px] border border-[rgba(255,255,255,.06)] p-1"
      style={{ background: 'var(--glass-bg)' }}
    >
      <div
        className="flex flex-1 items-center justify-center gap-[7px] rounded-[9px] py-2 text-[12.5px] text-[var(--text-1)]"
        style={{ background: 'linear-gradient(145deg,#1B4630,#14352A)', boxShadow: 'inset 0 1px 0 rgba(255,255,255,.08)' }}
      >
        <Sun className="h-[15px] w-[15px]" strokeWidth={1.8} /> Light
      </div>
      <div className="flex flex-1 items-center justify-center gap-[7px] rounded-[9px] py-2 text-[12.5px] text-[var(--text-2)]">
        <Moon className="h-[15px] w-[15px]" strokeWidth={1.8} /> Dark
      </div>
    </div>
  )
}

function ActiveBar() {
  return (
    <span
      aria-hidden
      className="absolute -left-px bottom-[11px] top-[11px] w-[3px] rounded-[3px] bg-[var(--accent)]"
      style={{ boxShadow: '0 0 10px var(--accent)' }}
    />
  )
}

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
    <div
      className="app-sidebar flex h-full flex-col px-5 pb-[22px] pt-[26px]"
      style={{ background: 'var(--sidebar-bg)', color: 'var(--text-1)' }}
    >
      <div
        className={cn(
          'mb-[22px] flex items-center justify-between gap-2 border-b border-[rgba(255,255,255,.06)] px-1 pb-6',
          collapsed && 'justify-center',
        )}
      >
        {!collapsed && (
          <img src={logo} alt="MY Trolley" className="block h-auto max-w-full" style={{ width: 'var(--logo-w)' }} />
        )}
        <button
          onClick={onToggleCollapse}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className="flex h-[18px] w-[18px] shrink-0 items-center justify-center text-[var(--text-2)] hover:text-[var(--text-1)]"
        >
          {collapsed ? (
            <ChevronsRight className="h-[18px] w-[18px]" strokeWidth={1.8} />
          ) : (
            <ChevronsLeft className="h-[18px] w-[18px]" strokeWidth={1.8} />
          )}
        </button>
      </div>

      <nav>
        <div>
          {!collapsed && <SectionLabel>Main menu</SectionLabel>}
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={onCloseMobile}
              title={item.label}
              className={({ isActive }) =>
                cn(itemClass, isActive ? activeClass : inactiveClass, collapsed && 'justify-center px-0')
              }
              style={{ height: 'var(--nav-h)', marginBottom: 'var(--nav-mb)' }}
            >
              {({ isActive }) => (
                <>
                  {isActive && <ActiveBar />}
                  <item.icon
                    className="h-[18px] w-[18px] shrink-0"
                    style={isActive ? { color: 'var(--accent)' } : undefined}
                    strokeWidth={1.8}
                  />
                  {!collapsed && <span className="truncate">{item.label}</span>}
                </>
              )}
            </NavLink>
          ))}
        </div>
        <div style={{ marginTop: '26px' }}>
          {!collapsed && <SectionLabel>Account</SectionLabel>}
          <NavLink
            to="/account"
            onClick={onCloseMobile}
            title="My Account"
            className={({ isActive }) =>
              cn(itemClass, isActive ? activeClass : inactiveClass, collapsed && 'justify-center px-0')
            }
            style={{ height: 'var(--nav-h)', marginBottom: 'var(--nav-mb)' }}
          >
            {({ isActive }) => (
              <>
                {isActive && <ActiveBar />}
                <UserRound
                  className="h-[18px] w-[18px] shrink-0"
                  style={isActive ? { color: 'var(--accent)' } : undefined}
                  strokeWidth={1.8}
                />
                {!collapsed && <span>My Account</span>}
              </>
            )}
          </NavLink>
          <button
            onClick={() => void signOut()}
            title="Logout"
            className={cn(itemClass, 'w-full', inactiveClass, collapsed && 'justify-center px-0')}
            style={{ height: 'var(--nav-h)' }}
          >
            <LogOut className="h-[18px] w-[18px] shrink-0" strokeWidth={1.8} />
            {!collapsed && <span>Logout</span>}
          </button>
        </div>
      </nav>

      <div className="flex-1" />
      {!collapsed && <SegmentedToggle />}
      <div
        className="flex items-center gap-3 rounded-[16px] border border-[rgba(255,255,255,.06)] p-[14px]"
        style={{ background: 'var(--tile-bg)' }}
      >
        <span
          className="flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-full font-bold"
          style={{ background: 'linear-gradient(145deg,#2FBF8B,#1B8F68)', color: 'var(--btn-text)' }}
        >
          {(user?.first_name || user?.username || 'A').slice(0, 1).toUpperCase()}
        </span>
        {!collapsed && (
          <div className="min-w-0">
            <p className="truncate text-[14px] font-bold text-[var(--text-1)]">
              {user?.full_name || user?.username || 'Admin user'}
            </p>
            <p className="truncate text-[12px] text-[var(--text-2)]">
              {user?.roles?.join(', ') || 'Administrator'}
            </p>
          </div>
        )}
      </div>
    </div>
  )

  return (
    <>
      <aside
        className={cn(
          'hidden shrink-0 overflow-hidden border-r border-[rgba(255,255,255,.06)] md:block',
          collapsed ? 'w-[76px]' : 'w-[300px]',
        )}
        style={{ position: 'sticky', top: 0, height: '100dvh', background: 'var(--sidebar-bg)' }}
      >
        {content}
      </aside>
      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          <button
            aria-label="Close navigation"
            className="absolute inset-0"
            style={{ background: 'rgba(27,26,23,.45)' }}
            onClick={onCloseMobile}
          />
          <div className="app-sidebar relative h-full w-[300px]" style={{ boxShadow: 'var(--modal-shadow)' }}>
            <button
              aria-label="Close navigation"
              onClick={onCloseMobile}
              className="absolute right-3 top-5 z-10 rounded-[9px] p-1 text-[var(--text-2)] hover:bg-[var(--glass-bg)]"
            >
              <X className="h-5 w-5" strokeWidth={1.8} />
            </button>
            {content}
          </div>
        </div>
      )}
    </>
  )
}
