import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Boxes,
  CheckCircle2,
  PauseCircle,
  Tag,
  Store as StoreIcon,
  Plus,
  Pencil,
  ArrowUpRight,
  AlertCircle,
  RefreshCw,
  Loader2,
} from 'lucide-react'
import type { ProductFilters, ProductListItem, Store } from '@/types'
import { catalogService } from '@/services/catalogService'
import { toError } from '@/services/apiClient'
import { formatDate } from '@/utils/format'
import { DashboardSkeleton, EmptyState } from '@/components/ui/feedback'
import { StoreSelect } from '@/components/ui/StoreSelect'
import { defaultVisibleStoreIds, reorderVisibleStoreIds } from '@/utils/storeSelection'

interface Metrics {
  total: number
  active: number
  inactive: number
  categories: number
  stores: number
  recent: ProductListItem[]
  creation_series: Array<{ date: string; count: number }>
}

const iconStroke = { strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }
const panel = 'rounded-[20px] p-[26px]'
const panelStyle: React.CSSProperties = {
  background: 'var(--card)',
  border: '1px solid var(--line)',
  boxShadow: 'var(--card-shadow)',
}
const heading = 'text-[16px] font-semibold text-[var(--text-1)]'
const sub = 'mt-[3px] text-[12.5px] text-[var(--text-2)]'
const link = 'text-[13px] font-medium text-[var(--accent-strong)] hover:brightness-110'
const tileStyle: React.CSSProperties = {
  background: 'var(--tile)',
  border: '1px solid var(--line)',
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span
      className="flex h-[32px] w-[32px] shrink-0 items-center justify-center rounded-[11px]"
      style={{ background: 'var(--chip-neutral-bg)', color: 'var(--chip-neutral-icon)' }}
    >
      {children}
    </span>
  )
}

function MiniTile({ icon, label, value }: { icon: React.ReactNode; label: string; value: number }) {
  return (
    <div className="flex items-center gap-3 rounded-[14px] px-[14px] py-[13px]" style={tileStyle}>
      <Chip>{icon}</Chip>
      <div className="min-w-0">
        <p className="text-[11.5px] text-[var(--text-2)]">{label}</p>
        <p className="text-[20px] font-bold leading-tight text-[var(--text-1)]">{value}</p>
      </div>
    </div>
  )
}

function AreaChart({ dailyCounts, total }: { dailyCounts: number[]; total: number }) {
  const perDay = dailyCounts.length === 30 ? dailyCounts : Array.from({ length: 30 }, () => 0)
  const days = perDay.length
  const baseline = Math.max(0, total - perDay.reduce((sum, count) => sum + count, 0))
  let running = baseline
  const values = perDay.map((count) => {
    running += count
    return running
  })

  const pad = 24
  const width = 520
  const height = 240
  const max = Math.max(1, ...values) * 1.25
  const innerW = width - pad * 2
  const innerH = height - pad * 2
  const points = values.map((value, index) => ({
    x: pad + (index / (days - 1)) * innerW,
    y: pad + innerH - (value / max) * innerH,
  }))

  const line = points.reduce((acc, point, index) => {
    if (index === 0) return `M ${point.x} ${point.y}`
    const previous = points[index - 1]
    const cx = (previous.x + point.x) / 2
    return `${acc} C ${cx} ${previous.y}, ${cx} ${point.y}, ${point.x} ${point.y}`
  }, '')
  const area = `${line} L ${points[points.length - 1].x} ${height - pad} L ${pad} ${height - pad} Z`
  const last = points[points.length - 1]

  return (
    <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="h-full min-h-[240px] w-full" aria-hidden>
      <defs>
        <linearGradient id="mt-area" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#EF3B3B" stopOpacity="0.22" />
          <stop offset="100%" stopColor="#EF3B3B" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[0, 1, 2, 3].map((row) => {
        const y = pad + row * (innerH / 3)
        return (
          <line key={row} x1={pad} x2={width - pad} y1={y} y2={y} stroke="rgba(45,30,15,.14)" strokeWidth="1" strokeDasharray="2 6" vectorEffect="non-scaling-stroke" />
        )
      })}
      <path d={area} fill="url(#mt-area)" />
      <path d={line} fill="none" stroke="#EF3B3B" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
      <circle cx={last.x} cy={last.y} r="12" fill="rgba(239,59,59,.18)" />
      <circle cx={last.x} cy={last.y} r="6" fill="#EF3B3B" />
    </svg>
  )
}

function StatusPill({ active }: { active: boolean }) {
  return (
    <span
      className="inline-flex h-[26px] items-center gap-[7px] rounded-full px-3 text-[12px] font-medium"
      style={active ? { color: 'var(--pos)', background: 'var(--pos-bg)' } : { color: 'var(--text-2)', background: 'var(--inactive-bg)' }}
    >
      <span className="h-[6px] w-[6px] rounded-full bg-current" />
      {active ? 'Active' : 'Inactive'}
    </span>
  )
}

function PipelineTile({ warm, icon, value, label, helper }: { warm: boolean; icon: React.ReactNode; value: number; label: string; helper: string }) {
  return (
    <div
      className="flex min-h-[178px] flex-col rounded-[16px] p-[18px]"
      style={warm ? { background: '#FEECEC', border: '1px solid rgba(240,16,16,.18)' } : tileStyle}
    >
      <span
        className="flex h-[38px] w-[38px] items-center justify-center rounded-[11px]"
        style={warm ? { background: '#FDE0E0', color: '#EF3B3B' } : { background: 'var(--chip-neutral-bg)', color: 'var(--chip-neutral-icon)' }}
      >
        {icon}
      </span>
      <p className="mt-auto text-[40px] font-bold leading-none tracking-[-1px] text-[var(--text-1)]">{value}</p>
      <p className="mt-1 text-[14px] font-semibold text-[var(--text-1)]">{label}</p>
      <p className="mt-[3px] text-[12px] text-[var(--text-2)]">{helper}</p>
    </div>
  )
}

export function DashboardPage() {
  const navigate = useNavigate()
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedStore, setSelectedStore] = useState<number | ''>('')
  const [visibleStoreIds, setVisibleStoreIds] = useState<number[]>([])
  const [stores, setStores] = useState<Store[]>([])
  const [statusTab, setStatusTab] = useState<'all' | 'active' | 'inactive'>('all')
  const [tabProducts, setTabProducts] = useState<ProductListItem[]>([])
  const [tabLoading, setTabLoading] = useState(false)
  const [tabError, setTabError] = useState<string | null>(null)
  const tabRequest = useRef(0)
  const firstTabRun = useRef(true)
  const [outOfStockCounts, setOutOfStockCounts] = useState<Record<number, number>>({})

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const summary = await catalogService.getDashboardSummary()
      setMetrics({
        total: summary.products.total,
        active: summary.products.active,
        inactive: summary.products.inactive,
        categories: summary.categories,
        stores: summary.stores,
        recent: summary.recent_products,
        creation_series: summary.creation_series,
      })
      setTabProducts(summary.recent_products)
      setStores(summary.store_availability)
      setOutOfStockCounts(
        Object.fromEntries(summary.store_availability.map((store) => [store.id, store.out_of_stock])),
      )
      setVisibleStoreIds((current) =>
        current.length ? current : defaultVisibleStoreIds(summary.store_availability.map((store) => store.id)),
      )
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
    if (firstTabRun.current) {
      firstTabRun.current = false
      return
    }
    const requestId = ++tabRequest.current
    setTabLoading(true)
    setTabError(null)
    const filters: ProductFilters = { ordering: '-created_at', page_size: 5 }
    if (statusTab === 'active') filters.is_active = true
    if (statusTab === 'inactive') filters.is_active = false
    void catalogService
      .listProducts(filters)
      .then((result) => {
        if (requestId !== tabRequest.current) return
        setTabProducts(result.results)
        setTabLoading(false)
      })
      .catch((err: unknown) => {
        if (requestId !== tabRequest.current) return
        setTabError(toError(err).message)
        setTabProducts([])
        setTabLoading(false)
      })
  }, [statusTab])

  if (loading) return <DashboardSkeleton />
  if (error) {
    return (
      <div
        className="flex flex-col items-center justify-center gap-3 rounded-[14px] py-10 text-center"
        style={{ background: 'var(--danger-bg)', border: '1px solid rgba(199,62,62,.2)', color: 'var(--danger-text)' }}
      >
        <AlertCircle className="h-6 w-6" {...iconStroke} />
        <p className="text-[14px] font-medium">{error}</p>
        <button onClick={() => void load()} className="flex items-center gap-2 rounded-[12px] border border-[var(--line)] bg-white px-4 py-2 text-[14px] text-[var(--text-1)]">
          <RefreshCw className="h-3.5 w-3.5" {...iconStroke} /> Retry
        </button>
      </div>
    )
  }

  const total = metrics?.total ?? 0
  const active = metrics?.active ?? 0
  const inactive = metrics?.inactive ?? 0
  const categories = metrics?.categories ?? 0
  const storeCount = metrics?.stores ?? 0
  const recent = metrics?.recent ?? []

  // Presentation-only ordering: unique store IDs, selected store first.
  const visibleStores = visibleStoreIds
    .map((id) => stores.find((store) => store.id === id))
    .filter((store): store is Store => Boolean(store))
    .slice(0, 3)

  const selectStore = (value: number | '') => {
    setSelectedStore(value)
    if (value === '') return
    setVisibleStoreIds((current) => reorderVisibleStoreIds(current, value))
  }

  const activity = recent.slice(0, 4).map((product) => {
    if (product.updated_at && product.updated_at !== product.created_at) {
      return { id: product.id, title: 'Product updated', name: product.name, time: formatDate(product.updated_at) }
    }
    if (!product.is_active) {
      return { id: product.id, title: 'Marked inactive', name: product.name, time: formatDate(product.created_at) }
    }
    return { id: product.id, title: 'Product added', name: product.name, time: formatDate(product.created_at) }
  })

  return (
    <div className="flex flex-col gap-[22px]">
      <div className="grid grid-cols-1 gap-[22px] min-[1280px]:grid-cols-[1.9fr_1.35fr]">
        <section className={`${panel} min-h-[330px] min-[1280px]:grid min-[1280px]:grid-cols-[300px_1fr] min-[1280px]:gap-5`} style={panelStyle}>
          <div className="flex flex-col">
            <h3 className={heading}>Catalogue summary</h3>
            <p className={sub}>Total across all stores</p>
            <p className="mt-[14px] text-[46px] font-bold leading-none tracking-[-1.2px] text-[var(--text-1)]">{total}</p>
            <p className="mt-2 text-[12.5px] text-[var(--text-2)]">{active} active products</p>
            <div className="mt-auto flex flex-col gap-3 pt-[14px]">
              <MiniTile icon={<Tag className="h-[18px] w-[18px]" {...iconStroke} />} label="Categories" value={categories} />
              <MiniTile icon={<StoreIcon className="h-[18px] w-[18px]" {...iconStroke} />} label="Stores" value={storeCount} />
            </div>
          </div>
          <div className="mt-6 min-h-[240px] min-[1280px]:mt-0">
            <AreaChart dailyCounts={(metrics?.creation_series ?? []).map((day) => day.count)} total={total} />
          </div>
        </section>

        <section className={panel} style={panelStyle}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className={heading}>Product pipeline</h3>
              <p className={sub}>Status of products across the catalogue</p>
            </div>
            <Link to="/products" className={`${link} flex shrink-0 items-center gap-1`} style={{ color: '#D62C2C' }}>
              View products <ArrowUpRight className="h-[15px] w-[15px]" {...iconStroke} />
            </Link>
          </div>
          <div className="mt-[22px] grid grid-cols-1 gap-[14px] sm:grid-cols-3">
            <PipelineTile warm icon={<Boxes className="h-[18px] w-[18px]" {...iconStroke} />} value={total} label="Total" helper="Products in catalogue" />
            <PipelineTile warm={false} icon={<CheckCircle2 className="h-[18px] w-[18px]" {...iconStroke} />} value={active} label="Active" helper="Live on stores" />
            <PipelineTile warm={false} icon={<PauseCircle className="h-[18px] w-[18px]" {...iconStroke} />} value={inactive} label="Inactive" helper="Hidden from stores" />
          </div>
        </section>
      </div>

      <section className={`${panel} !p-[26px]`} style={{ ...panelStyle, padding: '22px 26px 26px' }}>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h3 className={heading}>Store availability</h3>
            <p className={sub}>Available products by store</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <StoreSelect value={selectedStore} stores={stores} onChange={selectStore} />
            <Link to="/stores" className={`${link} flex items-center gap-1`}>
              View stores <ArrowUpRight className="h-[15px] w-[15px]" {...iconStroke} />
            </Link>
          </div>
        </div>
        {visibleStores.length === 0 && (
          <EmptyState title="No stores available" description="Add a store to see product availability." />
        )}
        <div className="mt-5 grid grid-cols-1 gap-[18px] md:grid-cols-2 min-[1280px]:grid-cols-3">
          {visibleStores.map((store, index) => {
            const iconTileStyles = [
              { background: 'linear-gradient(145deg, #11472F 0%, #0E3D28 100%)', boxShadow: '0 10px 22px rgba(14,61,40,.30)' },
              { background: 'linear-gradient(145deg, #258055 0%, #1F6B47 100%)', boxShadow: '0 10px 22px rgba(31,107,71,.28)' },
              { background: 'linear-gradient(145deg, #55B084 0%, #3E9A6E 100%)', boxShadow: '0 10px 22px rgba(62,154,110,.26)' },
            ]
            return (
              <div key={store.id} className="flex items-center gap-[18px] rounded-[18px] p-[18px]" style={tileStyle}>
                <div
                  className="flex h-[96px] w-[96px] shrink-0 items-center justify-center rounded-[16px]"
                  style={iconTileStyles[index % 3]}
                >
                  <StoreIcon className="h-[42px] w-[42px]" style={{ color: '#FFFFFF' }} strokeWidth={1.4} />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[15px] font-bold text-[var(--text-1)]">{store.name}</p>
                  <div className="my-[10px] flex flex-wrap gap-7">
                    <div>
                      <p className="text-[11.5px] text-[var(--text-2)]">Available</p>
                      <p className="text-[22px] font-bold text-[var(--text-1)]">{store.product_count ?? 0}</p>
                    </div>
                    <div>
                      <p className="text-[11.5px] text-[var(--text-2)]">Out of stock</p>
                      <p
                        className="text-[22px] font-bold"
                        style={
                          outOfStockCounts[store.id] === undefined
                            ? { color: 'var(--text-3)' }
                            : { color: 'var(--warn)' }
                        }
                      >
                        {outOfStockCounts[store.id] ?? '—'}
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => navigate(`/products?store=${store.id}`)}
                    className="rounded-[10px] border border-[rgba(45,30,15,.14)] bg-white px-[22px] py-2 text-[13px] text-[var(--text-1)] hover:bg-[var(--tile)]"
                  >
                    View inventory
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      </section>

      <div className="grid grid-cols-1 gap-[22px] min-[1280px]:grid-cols-[1.7fr_1fr]">
        <section className={panel} style={panelStyle}>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h3 className={heading}>Recent products</h3>
              <p className={sub}>Newest additions from the catalogue</p>
            </div>
            <Link to="/products" className={`${link} flex items-center gap-1`}>
              View all <ArrowUpRight className="h-[15px] w-[15px]" {...iconStroke} />
            </Link>
          </div>
          <div
            className="mb-[6px] mt-[18px] inline-flex gap-[6px] rounded-[13px] border border-[var(--line)] p-1"
            style={{ background: 'var(--tabs-bg)' }}
          >
            {[
              { key: 'all' as const, label: 'All', count: total },
              { key: 'active' as const, label: 'Active', count: active },
              { key: 'inactive' as const, label: 'Inactive', count: inactive },
            ].map((tab) => (
              <button
                type="button"
                key={tab.key}
                className="flex items-center rounded-[10px] px-4 py-[7px] text-[12.5px]"
                style={tab.key === statusTab ? { background: 'var(--dark)', color: '#FFFFFF' } : { color: 'var(--text-2)' }}
                onClick={() => setStatusTab(tab.key)}
              >
                {tab.label}
                <span
                  className="ml-[6px] rounded-full px-[7px] py-[2px] text-[11px]"
                  style={tab.key === statusTab ? { background: 'rgba(255,255,255,.18)' } : { background: 'rgba(45,30,15,.08)' }}
                >
                  {tab.count}
                </span>
              </button>
            ))}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-left">
              <thead>
                <tr>
                  {['Product', 'Category', 'Added', 'Status'].map((label) => (
                    <th key={label} className={`px-[10px] py-3 text-[11px] font-medium uppercase tracking-[.08em] text-[var(--text-3)] ${label === 'Product' ? 'w-[44%]' : ''}`}>
                      {label}
                    </th>
                  ))}
                  <th className="px-[10px] py-3" />
                </tr>
              </thead>
              <tbody>
                {tabProducts.slice(0, 3).map((product) => (
                  <tr key={product.id} className="h-[66px] border-t hover:bg-[var(--tile)]" style={{ borderColor: 'var(--line)' }}>
                    <td className="px-[10px]">
                      <div className="flex items-center gap-3">
                        <span className="flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-[11px] text-[var(--chip-neutral-icon)]" style={{ background: 'var(--chip-neutral-bg)' }}>
                          <Boxes className="h-[18px] w-[18px]" {...iconStroke} />
                        </span>
                        <span className="min-w-0">
                          <span className="block truncate text-[14px] font-medium text-[var(--text-1)]">{product.name}</span>
                          <span className="block text-[11.5px] text-[var(--text-3)]">Product record</span>
                        </span>
                      </div>
                    </td>
                    <td className="px-[10px] text-[14px] text-[var(--text-2)]">{product.category}</td>
                    <td className="px-[10px] text-[14px] text-[var(--text-2)]">{formatDate(product.created_at)}</td>
                    <td className="px-[10px]"><StatusPill active={product.is_active} /></td>
                    <td className="px-[10px] text-[16px] font-bold tracking-[2px] text-[var(--text-3)]">•••</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {tabLoading && (
              <p className="flex items-center justify-center gap-2 py-8 text-[13px] text-[var(--text-2)]">
                <Loader2 className="h-4 w-4 animate-spin" {...iconStroke} /> Loading products…
              </p>
            )}
            {tabError && <p className="py-8 text-center text-[13px] text-[var(--danger)]">{tabError}</p>}
            {!tabLoading && !tabError && tabProducts.length === 0 && (
              <p className="py-8 text-center text-[13px] text-[var(--text-2)]">No products yet</p>
            )}
          </div>
        </section>

        <section className={panel} style={panelStyle}>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h3 className={heading}>Recent activity</h3>
              <p className={sub}>Latest changes in your catalogue</p>
            </div>
            <Link to="/products" className={`${link} flex items-center gap-1`} style={{ color: '#D62C2C' }}>
              View all <ArrowUpRight className="h-[15px] w-[15px]" {...iconStroke} />
            </Link>
          </div>
          <div className="mt-3">
            {activity.map((item, index) => {
              const Icon = item.title === 'Product added' ? Plus : item.title === 'Product updated' ? Pencil : PauseCircle
              const warm = item.title !== 'Marked inactive'
              return (
                <div
                  key={`${item.id}-${index}`}
                  className={`flex items-center gap-[14px] py-[15px] ${index === activity.length - 1 ? '' : 'border-b'}`}
                  style={index === activity.length - 1 ? undefined : { borderColor: 'var(--line)' }}
                >
                  <span
                    className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full"
                    style={warm ? { background: '#FDE0E0', color: '#EF3B3B' } : { background: 'var(--chip-neutral-bg)', color: 'var(--chip-neutral-icon)' }}
                  >
                    <Icon className="h-[18px] w-[18px]" {...iconStroke} />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[14px] font-semibold text-[var(--text-1)]">{item.title}</span>
                    <span className="block truncate text-[12.5px] text-[var(--text-2)]">{item.name}</span>
                  </span>
                  <span className="shrink-0 whitespace-nowrap text-[11.5px] text-[var(--text-3)]">{item.time}</span>
                </div>
              )
            })}
          </div>
        </section>
      </div>
    </div>
  )
}
