import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from '@/layouts/AppShell'
import { LoginPage } from '@/pages/LoginPage'
import { DashboardSkeleton } from '@/components/ui/feedback'
import { useAuth } from '@/hooks/useAuth'

const DashboardPage = lazy(() => import('@/pages/DashboardPage').then((m) => ({ default: m.DashboardPage })))
const ProductsPage = lazy(() => import('@/pages/ProductsPage').then((m) => ({ default: m.ProductsPage })))
const ProductFormPage = lazy(() => import('@/pages/ProductFormPage').then((m) => ({ default: m.ProductFormPage })))
const CategoriesPage = lazy(() => import('@/pages/CategoriesPage').then((m) => ({ default: m.CategoriesPage })))
const StoresPage = lazy(() => import('@/pages/StoresPage').then((m) => ({ default: m.StoresPage })))
const AttributesPage = lazy(() => import('@/pages/AttributesPage').then((m) => ({ default: m.AttributesPage })))
const AccountPage = lazy(() => import('@/pages/AccountPage').then((m) => ({ default: m.AccountPage })))

function Protected({ children }: { children: React.ReactNode }) {
  const { token, loading } = useAuth()
  if (loading) return <DashboardSkeleton />
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  const { token } = useAuth()
  return (
    <Suspense fallback={<DashboardSkeleton />}>
      <Routes>
        <Route path="/login" element={token ? <Navigate to="/dashboard" replace /> : <LoginPage />} />
        <Route element={<Protected><AppShell /></Protected>}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/products" element={<ProductsPage />} />
          <Route path="/products/new" element={<ProductFormPage />} />
          <Route path="/products/:id/edit" element={<ProductFormPage />} />
          <Route path="/categories" element={<CategoriesPage />} />
          <Route path="/stores" element={<StoresPage />} />
          <Route path="/attributes" element={<AttributesPage />} />
          <Route path="/account" element={<AccountPage />} />
        </Route>
        <Route path="*" element={<Navigate to={token ? '/dashboard' : '/login'} replace />} />
      </Routes>
    </Suspense>
  )
}
