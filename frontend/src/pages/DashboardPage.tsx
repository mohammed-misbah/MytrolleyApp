import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Boxes, CheckCircle2, Tags, Store as StoreIcon, PackageSearch, ArrowUpRight } from 'lucide-react'
import type { ProductListItem, Store } from '@/types'
import { catalogService } from '@/services/catalogService'
import { toError } from '@/services/apiClient'
import { LoadingState, ErrorState } from '@/components/ui/feedback'
import { EmptyState } from '@/components/ui/feedback'
import { formatDate } from '@/utils/format'

interface Metrics {
  total: number
  active: number
  categories: number
  stores: number
  recent: ProductListItem[]
}

function MetricCard({
  label,
  value,
  icon: Icon,
  tone,
}: {
  label: string
  value: number
  icon: typeof Boxes
  tone: 'forest' | 'lime' | 'soft' | 'outline'
}) {
  const tones = {
    forest: 'bg-forest text-white',
    lime: 'bg-lime text-forest',
    soft: 'bg-lime-soft text-forest',
    outline: 'bg-white text-forest border border-line',
  }
  return (
    <div className="rounded-card border border-line bg-white p-5 shadow-card transition-shadow hover:shadow-float">
      <div className={`mb-4 inline-flex rounded-control p-2 ${tones[tone]}`}>
        <Icon className="h-5 w-5" />
      </div>
      <p className="text-3xl font-semibold tabular-nums text-ink">{value}</p>
      <p className="mt-1 text-xs font-medium uppercase tracking-wide text-subtle">{label}</p>
    </div>
  )
}

export function DashboardPage() {
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedStore, setSelectedStore] = useState<number | ''>('')
  const [availability, setAvailability] = useState(0)
  const [stores, setStores] = useState<Store[]>([])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [all, active, categories, storeList, recent] = await Promise.all([
        catalogService.listProducts({ page_size: 1 }),
        catalogService.listProducts({ is_active: true, page_size: 1 }),
        catalogService.listCategories(),
        catalogService.listStores(),
        catalogService.listProducts({ ordering: '-created_at', page_size: 5 }),
      ])
      setMetrics({
        total: all.count,
        active: active.count,
        categories: categories.length,
        stores: storeList.length,
        recent: recent.results,
      })
      setStores(storeList)
    } catch (err) {
      setError(toError(err).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (selectedStore === '') {
      setAvailability(0)
      return
    }
    void catalogService
      .listProducts({ store: Number(selectedStore), is_available: true, page_size: 1 })
      .then((r) => setAvailability(r.count))
      .catch(() => setAvailability(0))
  }, [selectedStore])

  if (loading) return <LoadingState label="Loading dashboard…" />
  if (error) return <ErrorState message={error} onRetry={() => void load()} />

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-card bg-forest px-6 py-8 text-white shadow-card md:px-10 md:py-10">
        <div className="absolute -right-10 -top-16 h-56 w-56 rounded-full bg-lime/10 blur-2xl" />
        <div className="relative flex flex-col justify-between gap-6 md:flex-row md:items-end">
          <div>
            <span className="inline-block rounded-full bg-lime px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-forest">
              MY Trolley workspace
            </span>
            <h2 className="mt-4 max-w-xl text-2xl font-semibold leading-tight md:text-3xl">
              Everything you need to manage your catalogue.
            </h2>
            <p className="mt-2 max-w-lg text-sm text-white/70">
              Monitor products, categories and store inventory from one place.
            </p>
          </div>
          <Link
            to="/products"
            className="inline-flex items-center gap-2 self-start rounded-control bg-white px-4 py-2.5 text-sm font-semibold text-forest transition-colors hover:bg-lime-soft"
          >
            Manage products <ArrowUpRight className="h-4 w-4" />
          </Link>
        </div>
      </section>

      <section className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <MetricCard label="Total products" value={metrics?.total ?? 0} icon={Boxes} tone="forest" />
        <MetricCard label="Active products" value={metrics?.active ?? 0} icon={CheckCircle2} tone="lime" />
        <MetricCard label="Categories" value={metrics?.categories ?? 0} icon={Tags} tone="soft" />
        <MetricCard label="Stores" value={metrics?.stores ?? 0} icon={StoreIcon} tone="outline" />
      </section>

      <section className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
        <div className="rounded-card border border-line bg-white p-5 shadow-card">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-ink">Recent products</h3>
              <p className="text-xs text-subtle">Newest additions from the catalogue</p>
            </div>
            <Link to="/products" className="text-xs font-medium text-forest hover:underline">
              View all
            </Link>
          </div>
          {metrics?.recent.length ? (
            <div className="divide-y divide-line">
              {metrics.recent.map((product) => (
                <div key={product.id} className="flex items-center gap-3 py-3 first:pt-0 last:pb-0">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-control bg-muted">
                    {product.primary_image?.image_url ? (
                      <img src={product.primary_image.image_url} alt="" className="h-full w-full object-cover" />
                    ) : (
                      <PackageSearch className="h-4 w-4 text-subtle" />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-ink">{product.name}</p>
                    <p className="truncate text-xs text-subtle">{product.category} · {formatDate(product.created_at)}</p>
                  </div>
                  <span
                    className={`rounded-full px-2 py-1 text-[11px] font-medium ${
                      product.is_active ? 'bg-lime-soft text-forest' : 'bg-muted text-subtle'
                    }`}
                  >
                    {product.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No products yet" description="Create your first product to see it here." />
          )}
        </div>

        <div className="rounded-card bg-forest-deep p-5 text-white shadow-card">
          <h3 className="text-sm font-semibold">Store inventory</h3>
          <p className="mt-1 text-xs text-white/60">Available products by store</p>
          <div className="mt-5 space-y-4">
            <label className="block">
              <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wide text-white/60">
                Select store
              </span>
              <select
                value={selectedStore}
                onChange={(e) => setSelectedStore(e.target.value ? Number(e.target.value) : '')}
                className="w-full rounded-control border border-white/15 bg-white/10 px-3 py-2 text-sm text-white focus:border-lime focus:outline-none"
              >
                <option value="">Choose a store…</option>
                {stores.map((store) => (
                  <option key={store.id} value={store.id} className="text-ink">
                    {store.name} ({store.code})
                  </option>
                ))}
              </select>
            </label>
            {selectedStore !== '' ? (
              <div className="rounded-card bg-white/5 p-4">
                <p className="text-3xl font-semibold tabular-nums text-lime">{availability}</p>
                <p className="mt-1 text-xs text-white/60">products available in this store</p>
              </div>
            ) : (
              <p className="text-xs text-white/50">Choose a store to see its availability count.</p>
            )}
          </div>
        </div>
      </section>
    </div>
  )
}
