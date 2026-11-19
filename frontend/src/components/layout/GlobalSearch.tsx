import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Loader2, Package, Search as SearchIcon, Tags } from 'lucide-react'
import { catalogService } from '@/services/catalogService'
import { toError } from '@/services/apiClient'
import type { Category, ProductListItem } from '@/types'

const DEBOUNCE_MS = 280
const MAX_RESULTS = 5

type Result =
  | { kind: 'product'; id: number; label: string; meta: string }
  | { kind: 'category'; id: number; label: string; meta: string }

export function GlobalSearch() {
  const navigate = useNavigate()
  const containerRef = useRef<HTMLDivElement>(null)
  const [query, setQuery] = useState('')
  const [products, setProducts] = useState<ProductListItem[]>([])
  const [categories, setCategories] = useState<Category[]>([])
  const [allCategories, setAllCategories] = useState<Category[] | null>(null)
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [activeIndex, setActiveIndex] = useState(-1)
  const latestRequest = useRef(0)

  // Categories have no server-side search endpoint; load the complete list once.
  useEffect(() => {
    let cancelled = false
    catalogService
      .listCategories()
      .then((rows) => {
        if (!cancelled) setAllCategories(rows)
      })
      .catch(() => {
        if (!cancelled) setAllCategories([])
      })
    return () => {
      cancelled = true
    }
  }, [])

  // Debounced server-side product search plus local category filtering.
  useEffect(() => {
    const term = query.trim()
    if (!term) {
      setProducts([])
      setCategories([])
      setLoading(false)
      setError(null)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    const timer = window.setTimeout(() => {
      const requestId = ++latestRequest.current
      void catalogService
        .listProducts({ search: term, page: 1, page_size: 20 })
        .then((page) => {
          // Server-side search already filtered these; take the closest matches.
          if (cancelled || requestId !== latestRequest.current) return
          setProducts(page.results.slice(0, MAX_RESULTS))
          setLoading(false)
        })
        .catch((err: unknown) => {
          if (cancelled || requestId !== latestRequest.current) return
          setError(toError(err).message)
          setProducts([])
          setLoading(false)
        })
    }, DEBOUNCE_MS)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [query])

  useEffect(() => {
    const term = query.trim().toLowerCase()
    if (!term || !allCategories) {
      setCategories([])
      return
    }
    setCategories(
      allCategories
        .filter((category) => category.name.toLowerCase().includes(term))
        .slice(0, MAX_RESULTS),
    )
  }, [query, allCategories])

  useEffect(() => {
    const onPointerDown = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onPointerDown)
    return () => document.removeEventListener('mousedown', onPointerDown)
  }, [])

  const results: Result[] = [
    ...products.map((product) => ({
      kind: 'product' as const,
      id: product.id,
      label: product.name,
      meta: product.category,
    })),
    ...categories.map((category) => ({
      kind: 'category' as const,
      id: category.id,
      label: category.name,
      meta: 'Category',
    })),
  ]

  useEffect(() => {
    setActiveIndex(-1)
  }, [query])

  const choose = (result: Result) => {
    setOpen(false)
    setQuery('')
    setActiveIndex(-1)
    if (result.kind === 'product') {
      navigate(`/products/${result.id}/edit`)
    } else {
      navigate('/categories')
    }
  }

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Escape') {
      setOpen(false)
      setActiveIndex(-1)
      return
    }
    if (!open || results.length === 0) return
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActiveIndex((index) => (index + 1) % results.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActiveIndex((index) => (index <= 0 ? results.length - 1 : index - 1))
    } else if (event.key === 'Enter' && activeIndex >= 0) {
      event.preventDefault()
      choose(results[activeIndex])
    }
  }

  const showDropdown = open && query.trim().length > 0
  const busy = loading || (!allCategories && query.trim().length > 0)

  return (
    <div ref={containerRef} className="relative">
      <div
        className="flex h-[46px] w-[360px] items-center gap-[10px] rounded-[14px] px-4"
        style={{
          background: 'var(--card)',
          border: '1px solid var(--line-input)',
          boxShadow: 'var(--header-shadow)',
        }}
      >
        <SearchIcon className="h-[18px] w-[18px] shrink-0 text-[var(--text-3)]" strokeWidth={1.8} />
        <input
          type="search"
          value={query}
          placeholder="Search products, categories..."
          className="h-full w-full min-w-0 bg-transparent text-[13.5px] text-[var(--text-1)] outline-none placeholder:text-[var(--text-3)]"
          onChange={(event) => {
            setQuery(event.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
        />
        {busy && <Loader2 className="h-4 w-4 shrink-0 animate-spin text-[var(--text-3)]" aria-hidden />}
      </div>

      {showDropdown && (
        <div
          role="listbox"
          className="absolute left-0 top-[52px] z-50 w-[360px] max-w-[calc(100vw-72px)] overflow-hidden rounded-[16px] p-2"
          style={{
            background: 'var(--card)',
            border: '1px solid var(--line)',
            boxShadow: 'var(--card-shadow)',
          }}
        >
          {error ? (
            <p className="px-3 py-3 text-[13px] text-[var(--danger)]">{error}</p>
          ) : busy && results.length === 0 ? (
            <p className="px-3 py-3 text-[13px] text-[var(--text-2)]">Searching…</p>
          ) : results.length === 0 ? (
            <p className="px-3 py-3 text-[13px] text-[var(--text-2)]">No matching products or categories.</p>
          ) : (
            <>
              {products.length > 0 && (
                <div className="mb-1">
                  <p className="px-3 pb-1 pt-1 text-[11px] font-semibold uppercase tracking-[.08em] text-[var(--text-3)]">
                    Products
                  </p>
                  {products.map((product, index) => (
                    <ResultRow
                      key={`product-${product.id}`}
                      icon={<Package className="h-[18px] w-[18px]" strokeWidth={1.8} />}
                      label={product.name}
                      meta={product.category}
                      active={activeIndex === index}
                      onClick={() =>
                        choose({
                          kind: 'product',
                          id: product.id,
                          label: product.name,
                          meta: product.category,
                        })
                      }
                    />
                  ))}
                </div>
              )}
              {categories.length > 0 && (
                <div>
                  <p className="px-3 pb-1 pt-1 text-[11px] font-semibold uppercase tracking-[.08em] text-[var(--text-3)]">
                    Categories
                  </p>
                  {categories.map((category, index) => (
                    <ResultRow
                      key={`category-${category.id}`}
                      icon={<Tags className="h-[18px] w-[18px]" strokeWidth={1.8} />}
                      label={category.name}
                      meta="Category"
                      active={activeIndex === products.length + index}
                      onClick={() =>
                        choose({
                          kind: 'category',
                          id: category.id,
                          label: category.name,
                          meta: 'Category',
                        })
                      }
                    />
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

function ResultRow({
  icon,
  label,
  meta,
  active,
  onClick,
}: {
  icon: React.ReactNode
  label: string
  meta: string
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      type="button"
      role="option"
      aria-selected={active}
      onClick={onClick}
      className="flex w-full items-center gap-3 rounded-[10px] px-3 py-2 text-left"
      style={active ? { background: 'var(--tile)' } : undefined}
    >
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] text-[var(--accent-strong)]" style={{ background: 'var(--warm-tile)' }}>
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-[13.5px] font-medium text-[var(--text-1)]">{label}</span>
        <span className="block truncate text-[11.5px] text-[var(--text-3)]">{meta}</span>
      </span>
    </button>
  )
}
