import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { Menu, UserRound, LogOut, ArrowUpRight } from 'lucide-react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { GlobalSearch } from './GlobalSearch'

const titles: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/products': 'Products',
  '/categories': 'Categories',
  '/stores': 'Stores',
  '/attributes': 'Product Attributes',
  '/account': 'My Account',
}

const glass: React.CSSProperties = {
  background: 'var(--card)',
  border: '1px solid var(--line-input)',
  boxShadow: 'var(--header-shadow)',
}

export function Header({ onOpenMobile }: { onOpenMobile: () => void }) {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { user, signOut } = useAuth()

  return (
    <header className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
      <div className="flex min-w-0 items-center gap-3">
        <button
          onClick={onOpenMobile}
          aria-label="Open navigation"
          className="flex h-[46px] w-[46px] items-center justify-center rounded-[14px] text-[var(--text-2)] md:hidden"
          style={glass}
        >
          <Menu className="h-[18px] w-[18px]" strokeWidth={1.8} />
        </button>
        <div className="min-w-0">
          <h1
            className="truncate text-[26px] font-[650] leading-[1.1] text-[var(--text-1)]"
            style={{ letterSpacing: '-.3px' }}
          >
            {titles[pathname] ?? (pathname.startsWith('/products/') ? 'Product details' : 'MY Trolley')}
          </h1>
          <p className="mt-[5px] truncate text-[14px] text-[var(--text-2)]">
            Product management administration
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <GlobalSearch />

        <Link
          to="/products"
          className="flex h-[46px] items-center gap-[9px] rounded-[14px] px-5 text-[14px] font-[650] text-white transition-[filter] hover:brightness-110"
          style={{ background: 'var(--dark)', boxShadow: 'var(--dark-shadow)' }}
        >
          Manage products
          <ArrowUpRight className="h-[17px] w-[17px]" strokeWidth={1.8} />
        </Link>

        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <button
              aria-label="Account menu"
              className="flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-full font-bold"
              style={{ background: 'var(--dark)', color: 'var(--avatar-letter)' }}
            >
              {(user?.first_name || user?.username || 'A').slice(0, 1).toUpperCase()}
            </button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content
              align="end"
              sideOffset={8}
              className="z-50 w-52 rounded-[16px] p-1.5"
              style={{ background: 'var(--card)', border: '1px solid var(--line)', boxShadow: 'var(--card-shadow)' }}
            >
              <DropdownMenu.Item
                onSelect={() => navigate('/account')}
                className="flex cursor-pointer items-center gap-2 rounded-[10px] px-3 py-2 text-[14px] text-[var(--text-1)] outline-none data-[highlighted]:bg-[var(--tile)]"
              >
                <UserRound className="h-[18px] w-[18px] text-[var(--accent-strong)]" strokeWidth={1.8} /> My Account
              </DropdownMenu.Item>
              <DropdownMenu.Separator className="my-1 h-px" style={{ background: 'var(--line)' }} />
              <DropdownMenu.Item
                onSelect={() => void signOut()}
                className="flex cursor-pointer items-center gap-2 rounded-[10px] px-3 py-2 text-[14px] text-[var(--danger)] outline-none data-[highlighted]:bg-[var(--danger-bg)]"
              >
                <LogOut className="h-[18px] w-[18px]" strokeWidth={1.8} /> Logout
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
      </div>
    </header>
  )
}
