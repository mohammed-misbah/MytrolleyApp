import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
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
import type { ProductListItem, Store } from '@/types'
import { catalogService } from '@/services/catalogService'
import { toError } from '@/services/apiClient'
import { formatDate } from '@/utils/format'

interface Metrics {
  total: number
  active: number
  categories: number
  stores: number
  recent: ProductListItem[]
}

const iconStroke = { strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const }
const panel = 'rounded-[22px] p-[26px]'
const panelStyle: React.CSSProperties = {
  background: 'var(--card)',
  border: '1px solid var(--line-card)',
  boxShadow: 'var(--card-shadow)',
}
const heading = 'text-[16px] font-semibold text-[var(--text-1)]'
const sub = 'mt-[3px] text-[12.5px] text-[var(--text-2)]'
const link = 'text-[13px] font-medium text-[var(--link)] hover:brightness-110'
const tileStyle: React.CSSProperties = {
  background: 'var(--tile)',
  border: '1px solid var(--line-tile)',
}

function Chip({ kind, children }: { kind: 'green' | 'warm' | 'neutral'; children: React.ReactNode }) {
  const bg = kind === 'green' ? 'var(--chip-green-bg)' : kind === 'warm' ? 'var(--chip-warm-bg)' : 'var(--chip-neutral-bg)'
  const color =
    kind === 'green' ? 'var(--chip-green-icon)' : kind === 'warm' ? 'var(--chip-warm-icon)' : 'var(--chip-neutral-icon)'
  return (
    <span className="flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-[11px]" style={{ background: bg, color }}>
      {children}
    </span>
  )
}

function MiniTile({ icon, label, value }: { icon: React.ReactNode; label: string; value: number }) {
  return (
    <div className="flex items-center gap-3 rounded-[14px] px-[14px] py-[13px]" style={tileStyle}>
      <Chip kind="green">{icon}</Chip>
      <div className="min-w-0">
        <p className="text-[11.5px] text-[var(--text-2)]">{label}</p>
        <p className="text-[20px] font-bold leading-tight text-[var(--text-1)]">{value}</p>
      </div>
    </div>
  )
}

function AreaChart({ products, total }: { products: ProductListItem[]; total: number }) {
  const days = 30
  const perDay = Array.from({ length: days }, () => 0)
  const now = Date.now()
  products.forEach((product) => {
    const time = new Date(product.created_at).getTime()
    const index = Math.floor((now - time) / 86_400_000)
    if (index >= 0 && index < days) perDay[days - 1 - index] += 1
  })
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
          <stop offset="0%" stopColor="#2FBF8B" stopOpacity="0.28" />
          <stop offset="100%" stopColor="#2FBF8B" stopOpacity="0" />
        </linearGradient>
      </defs>
      {[0, 1, 2, 3].map((row) => {
        const y = pad + row * (innerH / 3)
        return (
          <line key={row} x1={pad} x2={width - pad} y1={y} y2={y} stroke="rgba(18,45,32,.12)" strokeWidth="1" strokeDasharray="2 6" vectorEffect="non-scaling-stroke" />
        )
      })}
      <path d={area} fill="url(#mt-area)" />
      <path
        d={line}
        fill="none"
        stroke="var(--chart-line)"
        strokeWidth="2.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
      <circle cx={last.x} cy={last.y} r="12" fill="rgba(31,168,120,.18)" />
      <circle cx={last.x} cy={last.y} r="6" fill="var(--chart-line)" />
    </svg>
  )
}

function PipelineTile({ kind, icon, value, label, helper }: { kind: 'warm' | 'green' | 'neutral'; icon: React.ReactNode; value: number; label: string; helper: string }) {
  return (
    <div
      className="flex min-h-[178px] flex-col rounded-[16px] p-[18px]"
      style={
        kind === 'warm'
          ? { background: 'var(--warm-tile)', border: '1px solid var(--warm-border)' }
          : tileStyle
      }
    >
      <Chip kind={kind}>{icon}</Chip>
      <p className="mt-auto text-[40px] font-bold leading-none tracking-[-1px] text-[var(--text-1)]">{value}</p>
      <p className="mt-1 text-[14px] font-semibold text-[var(--text-1)]">{label}</p>
      <p className="mt-[3px] text-[12px] text-[var(--text-2)]">{helper}</p>
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

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-10 text-[14px] text-[var(--text-2)]">
        <Loader2 className="h-4 w-4 animate-spin" {...iconStroke} /> Loading dashboard…
      </div>
    )
  }
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-10 text-center">
        <AlertCircle className="h-6 w-6" style={{ color: 'var(--warm)' }} {...iconStroke} />
        <p className="text-[14px] font-medium text-[var(--text-1)]">{error}</p>
        <button onClick={() => void load()} className="flex items-center gap-2 rounded-[14px] border border-[var(--line-card)] bg-white px-4 py-2 text-[14px] text-[var(--text-1)]">
          <RefreshCw className="h-3.5 w-3.5" {...iconStroke} /> Retry
        </button>
      </div>
    )
  }

  const total = metrics?.total ?? 0
  const active = metrics?.active ?? 0
  const inactive = Math.max(0, total - active)
  const categories = metrics?.categories ?? 0
  const storeCount = metrics?.stores ?? 0
  const recent = metrics?.recent ?? []

  const activity = recent.slice(0, 4).map((product) => {
    if (product.updated_at && product.updated_at !== product.created_at) {
      return { id: product.id, title: 'Product updated', name: product.name, time: formatDate(product.updated_at), icon: Pencil }
    }
    if (!product.is_active) {
      return { id: product.id, title: 'Marked inactive', name: product.name, time: formatDate(product.created_at), icon: PauseCircle }
    }
    return { id: product.id, title: 'Product added', name: product.name, time: formatDate(product.created_at), icon: Plus }
  })

  return (
    <div className="flex flex-col gap-[22px]">
      <div className="grid grid-cols-1 gap-[22px] min-[1280px]:grid-cols-[1.9fr_1.35fr]">
        <section className={`${panel} min-h-[330px] min-[1280px]:grid min-[1280px]:grid-cols-[260px_1fr] min-[1280px]:gap-5`} style={panelStyle}>
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
            <AreaChart products={recent} total={total} />
          </div>
        </section>

        <section className={panel} style={panelStyle}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className={heading}>Product pipeline</h3>
              <p className={sub}>Status of products across the catalogue</p>
            </div>
            <Link to="/products" className={`${link} flex shrink-0 items-center gap-1`}>
              View products <ArrowUpRight className="h-[15px] w-[15px]" {...iconStroke} />
            </Link>
          </div>
          <div className="mt-[22px] grid grid-cols-1 gap-[14px] sm:grid-cols-3">
            <PipelineTile kind="warm" icon={<Boxes className="h-[18px] w-[18px]" {...iconStroke} />} value={total} label="Total" helper="Products in catalogue" />
            <PipelineTile kind="green" icon={<CheckCircle2 className="h-[18px] w-[18px]" {...iconStroke} />} value={active} label="Active" helper="Live on stores" />
            <PipelineTile kind="neutral" icon={<PauseCircle className="h-[18px] w-[18px]" {...iconStroke} />} value={inactive} label="Inactive" helper="Hidden from stores" />
          </div>
        </section>
      </div>

      <section className={panel} style={panelStyle}>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h3 className={heading}>Store availability</h3>
            <p className={sub}>Available products by store</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex h-[46px] items-center gap-2 rounded-[14px] border border-[var(--line-input)] bg-white px-4">
              <span className="text-[13.5px] text-[var(--text-2)]">Select store</span>
              <select
                value={selectedStore}
                onChange={(e) => setSelectedStore(e.target.value ? Number(e.target.value) : '')}
                className="max-w-[180px] bg-transparent text-[13.5px] text-[var(--text-1)] outline-none"
              >
                <option value="">All stores</option>
                {stores.map((store) => (
                  <option key={store.id} value={store.id}>
                    {store.name} ({store.code})
                  </option>
                ))}
              </select>
              <Chevron />
            </label>
            <Link to="/stores" className={`${link} flex items-center gap-1`}>
              View stores <ArrowUpRight className="h-[15px] w-[15px]" {...iconStroke} />
            </Link>
          </div>
        </div>
        {selectedStore !== '' && (
          <p className="mt-3 text-[12.5px] text-[var(--text-2)]">{availability} products available in the selected store</p>
        )}
        <div className="mt-5 grid grid-cols-1 gap-[18px] md:grid-cols-2 min-[1280px]:grid-cols-3">
          {stores.slice(0, 3).map((store, index) => {
            const warm = index % 3 === 2
            return (
              <div key={store.id} className="flex items-center gap-[18px] rounded-[18px] p-[18px]" style={tileStyle}>
                <div
                  className="flex h-[96px] w-[96px] shrink-0 items-center justify-center rounded-[16px]"
                  style={
                    warm
                      ? { background: 'linear-gradient(145deg,#F6D9AE,#EDBE82)', boxShadow: '0 10px 22px rgba(200,130,40,.22)' }
                      : { background: 'var(--brand-dark)', border: '1px solid rgba(63,217,162,.22)', boxShadow: '0 10px 22px rgba(10,31,21,.25)' }
                  }
                >
                  <StoreIcon className="h-[42px] w-[42px]" style={{ color: warm ? '#8A4F0B' : '#3FD9A2' }} strokeWidth={1.4} />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[15px] font-bold text-[var(--text-1)]">{store.name}</p>
                  <div className="my-[10px] flex flex-wrap gap-7">
                    <div>
                      <p className="text-[11.5px] text-[var(--text-2)]">Available</p>
                      <p className="text-[22px] font-bold text-[var(--text-1)]">{store.product_count ?? 0}</p>
                    </div>
                    <div>
                      <p className="text-[11.5px] text-[var(--text-2)]">Low stock</p>
                      <p className="text-[22px] font-bold text-[var(--warm)]">—</p>
                    </div>
                  </div>
                  <button type="button" className="rounded-[10px] border border-[rgba(18,45,32,.14)] bg-white px-[22px] py-2 text-[13px] text-[var(--text-1)] hover:bg-[var(--tile)]">
                    Review
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
          <div className="mb-[6px] mt-[18px] inline-flex gap-[6px] rounded-[13px] border border-[var(--line-card)] bg-[#F2F5F3] p-1">
            {[
              { label: 'All', count: total, active: true },
              { label: 'Active', count: active, active: false },
              { label: 'Inactive', count: inactive, active: false },
            ].map((tab) => (
              <span
                key={tab.label}
                className="flex items-center rounded-[10px] px-4 py-[7px] text-[12.5px]"
                style={tab.active ? { background: 'var(--brand-dark)', color: '#FFFFFF' } : { color: 'var(--text-2)' }}
              >
                {tab.label}
                <span
                  className="ml-[6px] rounded-full px-[7px] py-[2px] text-[11px]"
                  style={tab.active ? { background: 'rgba(255,255,255,.18)' } : { background: 'rgba(18,45,32,.08)' }}
                >
                  {tab.count}
                </span>
              </span>
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
                {recent.slice(0, 3).map((product) => (
                  <tr key={product.id} className="h-[66px] border-t hover:bg-[var(--tile)]" style={{ borderColor: 'var(--line-row)' }}>
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
                    <td className="px-[10px]">
                      <span
                        className="inline-flex h-[26px] items-center gap-[7px] rounded-full px-3 text-[12px] font-medium"
                        style={
                          product.is_active
                            ? { color: 'var(--link)', background: 'var(--positive-bg)' }
                            : { color: 'var(--text-2)', background: '#ECEFED' }
                        }
                      >
                        <span className="h-[6px] w-[6px] rounded-full bg-current" />
                        {product.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-[10px] text-[16px] font-bold tracking-[2px] text-[var(--text-3)]">•••</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {recent.length === 0 && <p className="py-8 text-center text-[13px] text-[var(--text-2)]">No products yet</p>}
          </div>
        </section>

        <section className={panel} style={panelStyle}>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h3 className={heading}>Recent activity</h3>
              <p className={sub}>Latest changes in your catalogue</p>
            </div>
            <Link to="/products" className={`${link} flex items-center gap-1`}>
              View all <ArrowUpRight className="h-[15px] w-[15px]" {...iconStroke} />
            </Link>
          </div>
          <div className="mt-3">
            {activity.map((item, index) => {
              const Icon = item.icon
              const neutral = item.title === 'Marked inactive'
              return (
                <div
                  key={`${item.id}-${index}`}
                  className={`flex items-center gap-[14px] py-[15px] ${index === activity.length - 1 ? '' : 'border-b'}`}
                  style={index === activity.length - 1 ? undefined : { borderColor: 'var(--line-row)' }}
                >
                  <span
                    className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full"
                    style={
                      neutral
                        ? { background: 'var(--chip-neutral-bg)', color: 'var(--chip-neutral-icon)' }
                        : item.title === 'Product added'
                          ? { background: 'var(--chip-green-bg)', color: 'var(--chip-green-icon)' }
                          : { background: 'var(--chip-warm-bg)', color: 'var(--chip-warm-icon)' }
                    }
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

function Chevron() {
  return (
    <svg className="h-[15px] w-[15px] shrink-0 text-[var(--text-2)]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="m6 9 6 6 6-6" />
    </svg>
  )
}
