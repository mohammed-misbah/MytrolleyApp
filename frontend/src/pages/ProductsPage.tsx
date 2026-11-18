import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Eye, Pencil, Trash2, ChevronLeft, ChevronRight, PackageSearch } from 'lucide-react'
import { toast } from 'sonner'
import type { Category, Paginated, ProductDetail, ProductFilters, ProductListItem, Store } from '@/types'
import { catalogService } from '@/services/catalogService'
import { toError } from '@/services/apiClient'
import { Button } from '@/components/ui/button'
import { Input, Select } from '@/components/ui/field'
import { ConfirmDialog, Dialog } from '@/components/ui/overlay'
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/feedback'
import { formatDate, formatMoney } from '@/utils/format'
import { validatePriceRange } from '@/utils/validation'

export function ProductsPage() {
  const [filters, setFilters] = useState<ProductFilters>({ page: 1, page_size: 10, ordering: 'name' })
  const [data, setData] = useState<Paginated<ProductListItem> | null>(null)
  const [categories, setCategories] = useState<Category[]>([])
  const [stores, setStores] = useState<Store[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [minInput, setMinInput] = useState('')
  const [maxInput, setMaxInput] = useState('')
  const [detail, setDetail] = useState<ProductDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [toDelete, setToDelete] = useState<ProductListItem | null>(null)
  const [deleting, setDeleting] = useState(false)

  // A single source of truth for "a real store is selected". Price inputs,
  // price sorting and price filtering all depend on this value. Using a
  // derived boolean avoids drift between the disabled state and the request
  // guard (the root cause of price fields becoming stuck as disabled).
  const selectedStoreId = filters.store
  const storeSelected =
    selectedStoreId !== undefined &&
    selectedStoreId !== null &&
    Number(selectedStoreId) > 0

  // Validation is computed from the draft input values, so messages appear
  // while typing and clear automatically as soon as the values become valid.
  // Applied filters change only on Search/Enter, so invalid drafts never
  // replace previously valid results.
  const priceError = validatePriceRange(minInput, maxInput)
  const load = useCallback(async () => {
    // Defense in depth: invalid applied filters never reach the backend, and
    // existing results are preserved rather than replaced by an empty state.
    if (
      validatePriceRange(filters.min_price, filters.max_price) ||
      ((filters.ordering === 'price' || filters.ordering === '-price') && !storeSelected) ||
      ((filters.min_price !== undefined || filters.max_price !== undefined) && !storeSelected)
    ) {
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      setData(await catalogService.listProducts(filters))
    } catch (err) {
      setError(toError(err).message)
    } finally {
      setLoading(false)
    }
  }, [filters, storeSelected])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    void catalogService.listCategories().then(setCategories).catch(() => undefined)
    void catalogService.listStores().then(setStores).catch(() => undefined)
  }, [])

  const applySearch = () => {
    if (validatePriceRange(minInput, maxInput)) return
    setFilters((f) => ({
      ...f,
      search: search || undefined,
      min_price: minInput.trim() || undefined,
      max_price: maxInput.trim() || undefined,
      page: 1,
    }))
  }

  const openDetail = async (id: number) => {
    setDetailLoading(true)
    try {
      setDetail(await catalogService.getProduct(id))
    } catch (err) {
      toast.error(toError(err).message)
    } finally {
      setDetailLoading(false)
    }
  }

  const confirmDelete = async () => {
    if (!toDelete) return
    setDeleting(true)
    try {
      await catalogService.deleteProduct(toDelete.id)
      toast.success('Product deactivated successfully.')
      setToDelete(null)
      await load()
    } catch (err) {
      toast.error(toError(err).message)
    } finally {
      setDeleting(false)
    }
  }

  const totalPages = data?.total_pages ?? 0
  const page = data?.page ?? 1

  return (
    <div className="space-y-5">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <h2 className="text-xl font-semibold text-ink">Products</h2>
          <p className="text-sm text-subtle">Manage your catalogue and store-specific inventory.</p>
        </div>
        <Link to="/products/new">
          <Button>Add product</Button>
        </Link>
      </div>

      <div className="rounded-card border border-line bg-white p-4 shadow-card">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <div className="relative sm:col-span-2 lg:col-span-1">
            <Input
              placeholder="Search products…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && applySearch()}
            />
          </div>
          <Select
            value={filters.store ?? ''}
            onChange={(e) =>
              setFilters((f) => {
                const store = e.target.value ? Number(e.target.value) : undefined
                // Returning to All stores clears both draft and applied price
                // values and resets price sorting to the default Name sort.
                if (!store) {
                  setMinInput('')
                  setMaxInput('')
                  return {
                    ...f,
                    store: undefined,
                    ordering: f.ordering === 'price' || f.ordering === '-price' ? 'name' : f.ordering,
                    min_price: undefined,
                    max_price: undefined,
                    page: 1,
                  }
                }
                // Switching between specific stores keeps valid inputs and
                // sorting; results are recalculated from the new store's prices.
                return { ...f, store, page: 1 }
              })
            }
          >
            <option value="">All stores</option>
            {stores.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </Select>
          <Select
            value={filters.category ?? ''}
            onChange={(e) =>
              setFilters((f) => ({ ...f, category: e.target.value ? Number(e.target.value) : undefined, page: 1 }))
            }
          >
            <option value="">All categories</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </Select>
          <Select
            value={filters.is_active === undefined ? '' : String(filters.is_active)}
            onChange={(e) =>
              setFilters((f) => ({
                ...f,
                is_active: e.target.value === '' ? undefined : e.target.value === 'true',
                page: 1,
              }))
            }
          >
            <option value="">Any status</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </Select>
          <div>
            <Select
              value={filters.ordering ?? 'name'}
              onChange={(e) => setFilters((f) => ({ ...f, ordering: e.target.value, page: 1 }))}
            >
              <option value="name">Name (A–Z)</option>
              <option value="-name">Name (Z–A)</option>
              <option value="created_at">Oldest first</option>
              <option value="-created_at">Newest first</option>
              <option value="price" disabled={!storeSelected}>Price (Low to High)</option>
              <option value="-price" disabled={!storeSelected}>Price (High to Low)</option>
            </Select>
            {!storeSelected && (
              <p className="mt-1 text-[11px] text-subtle">Select a store to sort products by price.</p>
            )}
          </div>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button size="sm" variant="outline" onClick={applySearch}>Search</Button>
          <Input
            className="w-24"
            type="text"
            inputMode="decimal"
            placeholder="Min AED"
            disabled={!storeSelected}
            value={minInput}
            onChange={(e) => setMinInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && applySearch()}
          />
          <Input
            className="w-24"
            type="text"
            inputMode="decimal"
            placeholder="Max AED"
            disabled={!storeSelected}
            value={maxInput}
            onChange={(e) => setMaxInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && applySearch()}
          />
          <Select
            className="w-40"
            value={filters.page_size ?? 10}
            onChange={(e) => setFilters((f) => ({ ...f, page_size: Number(e.target.value), page: 1 }))}
          >
            {[5, 10, 20, 50].map((n) => (
              <option key={n} value={n}>{n} per page</option>
            ))}
          </Select>
          {(filters.search || filters.store || filters.category || filters.min_price || filters.max_price || minInput || maxInput) && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setSearch('')
                setMinInput('')
                setMaxInput('')
                setFilters({ page: 1, page_size: filters.page_size, ordering: 'name' })
              }}
            >
              Clear filters
            </Button>
          )}
          {!storeSelected && (
            <p className="w-full text-[11px] text-subtle">Select a store to filter products by price.</p>
          )}
          {priceError && (
            <p className="w-full text-xs font-medium text-danger">{priceError}</p>
          )}
        </div>
      </div>

      <div className="overflow-hidden rounded-card border border-line bg-white shadow-card">
        {loading ? (
          <LoadingState label="Loading products…" />
        ) : error ? (
          <ErrorState message={error} onRetry={() => void load()} />
        ) : !data || data.results.length === 0 ? (
          <EmptyState title="No products found" description="Adjust your filters or add a new product." />
        ) : (
          <>
            <div className="hidden overflow-x-auto md:block">
              <table className="w-full min-w-[900px] text-left text-sm">
                <thead className="bg-muted text-[11px] uppercase tracking-wide text-subtle">
                  <tr>
                    <th className="px-4 py-3 font-semibold">Image</th>
                    <th className="px-4 py-3 font-semibold">Product</th>
                    <th className="px-4 py-3 font-semibold">Category</th>
                    <th className="px-4 py-3 font-semibold">Attributes</th>
                    <th className="px-4 py-3 font-semibold">Stores</th>
                    <th className="px-4 py-3 font-semibold">Status</th>
                    <th className="px-4 py-3 text-right font-semibold">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {data.results.map((product) => (
                    <tr key={product.id} className="transition-colors hover:bg-canvas/70">
                      <td className="px-4 py-3">
                        <div className="flex h-11 w-11 items-center justify-center overflow-hidden rounded-control bg-muted">
                          {product.primary_image?.image_url ? (
                            <img src={product.primary_image.image_url} alt="" className="h-full w-full object-cover" />
                          ) : (
                            <PackageSearch className="h-4 w-4 text-subtle" />
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <p className="font-medium text-ink">{product.name}</p>
                        <p className="text-xs text-subtle">{product.slug} · {formatDate(product.created_at)}</p>
                      </td>
                      <td className="px-4 py-3 text-subtle">{product.category}</td>
                      <td className="px-4 py-3">
                        <span className="text-xs text-subtle">View details</span>
                      </td>
                      <td className="px-4 py-3">
                        {product.store_price ? (
                          <span className="text-xs text-ink">{formatMoney(product.store_price.price)}</span>
                        ) : (
                          <span className="text-xs text-subtle">Select store</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${
                            product.is_active ? 'bg-lime-soft text-forest' : 'bg-muted text-subtle'
                          }`}
                        >
                          {product.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex justify-end gap-1">
                          <Button variant="ghost" size="icon" title="View" onClick={() => void openDetail(product.id)}>
                            <Eye className="h-4 w-4" />
                          </Button>
                          <Link to={`/products/${product.id}/edit`}>
                            <Button variant="ghost" size="icon" title="Edit"><Pencil className="h-4 w-4" /></Button>
                          </Link>
                          <Button variant="ghost" size="icon" title="Delete" onClick={() => setToDelete(product)}>
                            <Trash2 className="h-4 w-4 text-danger" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="divide-y divide-line md:hidden">
              {data.results.map((product) => (
                <div key={product.id} className="p-4">
                  <div className="flex items-center gap-3">
                    <div className="flex h-12 w-12 items-center justify-center overflow-hidden rounded-control bg-muted">
                      {product.primary_image?.image_url ? (
                        <img src={product.primary_image.image_url} alt="" className="h-full w-full object-cover" />
                      ) : (
                        <PackageSearch className="h-5 w-5 text-subtle" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium text-ink">{product.name}</p>
                      <p className="text-xs text-subtle">{product.category}</p>
                    </div>
                    <span className={`rounded-full px-2 py-1 text-[11px] font-medium ${product.is_active ? 'bg-lime-soft text-forest' : 'bg-muted text-subtle'}`}>
                      {product.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                  <div className="mt-3 flex gap-2">
                    <Button size="sm" variant="outline" onClick={() => void openDetail(product.id)}>View</Button>
                    <Link to={`/products/${product.id}/edit`}><Button size="sm" variant="outline">Edit</Button></Link>
                    <Button size="sm" variant="outline" onClick={() => setToDelete(product)}>Delete</Button>
                  </div>
                </div>
              ))}
            </div>

            <div className="flex items-center justify-between border-t border-line px-4 py-3">
              <p className="text-xs text-subtle">
                {data.count} products · page {page} of {totalPages || 1}
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setFilters((f) => ({ ...f, page: (f.page ?? 1) - 1 }))}
                >
                  <ChevronLeft className="h-4 w-4" /> Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setFilters((f) => ({ ...f, page: (f.page ?? 1) + 1 }))}
                >
                  Next <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </>
        )}
      </div>

      <Dialog open={Boolean(detail)} onOpenChange={(open) => !open && setDetail(null)} title="Product details">
        {detailLoading ? (
          <LoadingState />
        ) : detail ? (
          <div className="max-h-[70vh] space-y-5 overflow-y-auto pr-1">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div><p className="text-xs text-subtle">Name</p><p className="font-medium">{detail.name}</p></div>
              <div><p className="text-xs text-subtle">Category</p><p className="font-medium">{detail.category.name}</p></div>
              <div className="col-span-2"><p className="text-xs text-subtle">Description</p><p>{detail.description || '—'}</p></div>
            </div>
            {detail.attributes.length > 0 && (
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-subtle">Attributes</p>
                <div className="flex flex-wrap gap-2">
                  {detail.attributes.map((a) => (
                    <span key={a.id} className="rounded-full bg-muted px-3 py-1 text-xs text-ink">
                      {a.name}: {a.value}
                    </span>
                  ))}
                </div>
              </div>
            )}
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-subtle">Store-specific pricing</p>
              {detail.store_associations.length ? (
                <div className="divide-y divide-line rounded-card border border-line">
                  {detail.store_associations.map((a) => (
                    <div key={a.id} className="flex items-center justify-between px-3 py-2.5 text-sm">
                      <span className="font-medium">{a.store.name} <span className="text-xs text-subtle">({a.store.code})</span></span>
                      <span className="tabular-nums">{formatMoney(a.price)} · Qty {a.quantity} · {a.is_available ? 'Available' : 'Unavailable'}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-subtle">No store associations yet.</p>
              )}
            </div>
            {detail.images.length > 0 && (
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-subtle">Images</p>
                <div className="grid grid-cols-3 gap-2">
                  {detail.images.map((image) => (
                    <img key={image.id} src={image.image_url} alt={image.alt_text} className="h-20 w-full rounded-control object-cover" />
                  ))}
                </div>
              </div>
            )}
            <div className="flex justify-end gap-2">
              <Link to={`/products/${detail.id}/edit`}>
                <Button onClick={() => setDetail(null)}>Edit product</Button>
              </Link>
            </div>
          </div>
        ) : null}
      </Dialog>

      <ConfirmDialog
        open={Boolean(toDelete)}
        onOpenChange={(open) => !open && setToDelete(null)}
        title="Deactivate product?"
        description={`"${toDelete?.name ?? ''}" will be marked inactive. Existing records remain intact.`}
        onConfirm={() => void confirmDelete()}
        loading={deleting}
      />
    </div>
  )
}
