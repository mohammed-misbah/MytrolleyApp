import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Toaster } from 'sonner'
import { Header } from '@/components/layout/Header'
import { Sidebar } from '@/components/layout/Sidebar'

export function AppShell() {
  const [collapsed, setCollapsed] = useState(false)
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="flex min-h-screen" style={{ background: 'var(--page)' }}>
      <Sidebar
        collapsed={collapsed}
        mobileOpen={mobileOpen}
        onToggleCollapse={() => setCollapsed((v) => !v)}
        onCloseMobile={() => setMobileOpen(false)}
      />
      <div
        className="flex min-w-0 flex-1 flex-col gap-[22px] overflow-y-auto px-9 py-[30px]"
        style={{
          height: '100dvh',
          scrollbarColor: 'rgba(255,255,255,.14) transparent',
          scrollbarWidth: 'thin',
        }}
      >
        <Header onOpenMobile={() => setMobileOpen(true)} />
        <main className="flex w-full flex-1 flex-col gap-[22px]">
          <Outlet />
        </main>
      </div>
      <Toaster position="top-right" richColors closeButton />
    </div>
  )
}
