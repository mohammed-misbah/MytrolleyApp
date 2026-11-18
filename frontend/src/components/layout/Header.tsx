import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { ChevronDown, LogOut, Menu, UserRound } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'

const titles: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/products': 'Products',
  '/categories': 'Categories',
  '/stores': 'Stores',
  '/attributes': 'Product Attributes',
  '/account': 'My Account',
}

export function Header({ onOpenMobile }: { onOpenMobile: () => void }) {
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { user, signOut } = useAuth()

  return (
    <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-line bg-white/95 px-4 backdrop-blur md:px-6">
      <div className="flex items-center gap-3">
        <button
          onClick={onOpenMobile}
          aria-label="Open navigation"
          className="rounded-control p-2 text-subtle hover:bg-muted lg:hidden"
        >
          <Menu className="h-5 w-5" />
        </button>
        <div>
          <h1 className="text-base font-semibold text-ink md:text-lg">
            {titles[pathname] ?? (pathname.startsWith('/products/') ? 'Product details' : 'MY Trolley')}
          </h1>
          <p className="hidden text-xs text-subtle sm:block">Product management administration</p>
        </div>
      </div>

      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <button
            className="flex items-center gap-2 rounded-control px-2 py-1.5 transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lime"
            aria-label="Account menu"
          >
            <span className="hidden text-sm font-medium text-ink sm:inline">
              {user?.full_name || user?.username || 'Account'}
            </span>
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-forest text-sm font-semibold text-white">
              {(user?.first_name || user?.username || 'A').slice(0, 1).toUpperCase()}
            </span>
            <ChevronDown className="hidden h-3.5 w-3.5 text-subtle sm:block" />
          </button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content
            align="end"
            sideOffset={8}
            className="z-50 w-52 rounded-card border border-line bg-white p-1.5 shadow-float"
          >
            <DropdownMenu.Item
              onSelect={() => navigate('/account')}
              className="flex cursor-pointer items-center gap-2 rounded-control px-3 py-2 text-sm text-ink outline-none data-[highlighted]:bg-lime-soft"
            >
              <UserRound className="h-4 w-4 text-forest" /> My Account
            </DropdownMenu.Item>
            <DropdownMenu.Separator className="my-1 h-px bg-line" />
            <DropdownMenu.Item
              onSelect={() => void signOut()}
              className="flex cursor-pointer items-center gap-2 rounded-control px-3 py-2 text-sm text-danger outline-none data-[highlighted]:bg-danger/10"
            >
              <LogOut className="h-4 w-4" /> Logout
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
    </header>
  )
}
