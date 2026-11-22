import { apiClient } from './apiClient'
import { cachedGet, dedupGet } from './requestCache'
import type {
  AssociationWrite,
  DashboardSummary,
  AttributeWrite,
  Category,
  CategoryWrite,
  Paginated,
  ProductAttribute,
  ProductDetail,
  ProductFilters,
  ProductImage,
  ProductListItem,
  ProductStore,
  ProductWrite,
  Store,
  StoreWrite,
} from '@/types'

function paramsFrom(filters: ProductFilters): Record<string, string | number | boolean> {
  const params: Record<string, string | number | boolean> = {}
  const entries = Object.entries(filters).filter(([, v]) => v !== undefined && v !== '' && v !== null)
  for (const [key, value] of entries) params[key] = value as string | number | boolean
  return params
}

export const catalogService = {
  // Dashboard (single bounded-cost request)
  getDashboardSummary: (): Promise<DashboardSummary> =>
    cachedGet('dashboard:summary', async () => (await apiClient.get<DashboardSummary>('/dashboard/summary/')).data),

  // Categories
  listCategories: (): Promise<Category[]> =>
    cachedGet('categories', async () => (await apiClient.get<Category[]>('/categories/')).data),
  getCategory: (id: number): Promise<Category> =>
    dedupGet(`category:${id}`, async () => (await apiClient.get<Category>(`/categories/${id}/`)).data),
  createCategory: async (body: CategoryWrite): Promise<Category> =>
    (await apiClient.post<Category>('/categories/', body)).data,
  updateCategory: async (id: number, body: Partial<CategoryWrite>): Promise<Category> =>
    (await apiClient.patch<Category>(`/categories/${id}/`, body)).data,
  deleteCategory: async (id: number): Promise<void> => {
    await apiClient.delete(`/categories/${id}/`)
  },

  // Stores
  listStores: (): Promise<Store[]> =>
    cachedGet('stores', async () => (await apiClient.get<Store[]>('/stores/')).data),
  getStore: (id: number): Promise<Store> =>
    dedupGet(`store:${id}`, async () => (await apiClient.get<Store>(`/stores/${id}/`)).data),
  createStore: async (body: StoreWrite): Promise<Store> => (await apiClient.post<Store>('/stores/', body)).data,
  updateStore: async (id: number, body: Partial<StoreWrite>): Promise<Store> =>
    (await apiClient.patch<Store>(`/stores/${id}/`, body)).data,
  deleteStore: async (id: number): Promise<void> => {
    await apiClient.delete(`/stores/${id}/`)
  },

  // Products
  listProducts: (filters: ProductFilters): Promise<Paginated<ProductListItem>> => {
    const params = paramsFrom(filters)
    const key = JSON.stringify(Object.entries(params).sort(([left], [right]) => left.localeCompare(right)))
    return dedupGet(`products:${key}`, async () =>
      (await apiClient.get<Paginated<ProductListItem>>('/products/', { params })).data,
    )
  },
  getProduct: (id: number): Promise<ProductDetail> =>
    dedupGet(`product:${id}`, async () => (await apiClient.get<ProductDetail>(`/products/${id}/`)).data),
  createProduct: async (body: ProductWrite): Promise<ProductDetail> =>
    (await apiClient.post<ProductDetail>('/products/', body)).data,
  /** Atomic creation with images, attributes and store pricing in one request. */
  createProductWithRelations: async (form: FormData): Promise<ProductDetail> =>
    (await apiClient.post<ProductDetail>('/products/create-with-relations/', form)).data,
  updateProduct: async (id: number, body: Partial<ProductWrite>): Promise<ProductDetail> =>
    (await apiClient.patch<ProductDetail>(`/products/${id}/`, body)).data,
  deleteProduct: async (id: number): Promise<void> => {
    await apiClient.delete(`/products/${id}/`)
  },

  // Attributes
  listAttributes: (productId: number): Promise<ProductAttribute[]> =>
    dedupGet(`attributes:${productId}`, async () =>
      (await apiClient.get<ProductAttribute[]>(`/products/${productId}/attributes/`)).data,
    ),
  createAttribute: async (productId: number, body: AttributeWrite): Promise<ProductAttribute> =>
    (await apiClient.post<ProductAttribute>(`/products/${productId}/attributes/`, body)).data,
  updateAttribute: async (productId: number, id: number, body: Partial<AttributeWrite>): Promise<ProductAttribute> =>
    (await apiClient.patch<ProductAttribute>(`/products/${productId}/attributes/${id}/`, body)).data,
  deleteAttribute: async (productId: number, id: number): Promise<void> => {
    await apiClient.delete(`/products/${productId}/attributes/${id}/`)
  },

  // Images (multipart — Authorization and the multipart boundary are added by apiClient)
  listImages: (productId: number): Promise<ProductImage[]> =>
    dedupGet(`images:${productId}`, async () =>
      (await apiClient.get<ProductImage[]>(`/products/${productId}/images/`)).data,
    ),
  uploadImage: async (
    productId: number,
    file: File,
    meta?: Partial<Pick<ProductImage, 'alt_text' | 'display_order' | 'is_primary'>>,
  ): Promise<ProductImage> => {
    const form = new FormData()
    form.append('image', file)
    if (meta?.alt_text) form.append('alt_text', meta.alt_text)
    if (meta?.display_order !== undefined) form.append('display_order', String(meta.display_order))
    if (meta?.is_primary !== undefined) form.append('is_primary', String(meta.is_primary))
    return (await apiClient.post<ProductImage>(`/products/${productId}/images/`, form)).data
  },
  updateImage: async (
    productId: number,
    id: number,
    meta: Partial<Pick<ProductImage, 'alt_text' | 'display_order' | 'is_primary'>>,
  ): Promise<ProductImage> => {
    const form = new FormData()
    if (meta.alt_text !== undefined) form.append('alt_text', meta.alt_text)
    if (meta.display_order !== undefined) form.append('display_order', String(meta.display_order))
    if (meta.is_primary !== undefined) form.append('is_primary', String(meta.is_primary))
    return (await apiClient.patch<ProductImage>(`/products/${productId}/images/${id}/`, form)).data
  },
  deleteImage: async (productId: number, id: number): Promise<void> => {
    await apiClient.delete(`/products/${productId}/images/${id}/`)
  },

  // Product-store associations
  listAssociations: (productId: number): Promise<ProductStore[]> =>
    dedupGet(`associations:${productId}`, async () =>
      (await apiClient.get<ProductStore[]>(`/products/${productId}/stores/`)).data,
    ),
  createAssociation: async (productId: number, body: AssociationWrite): Promise<ProductStore> =>
    (await apiClient.post<ProductStore>(`/products/${productId}/stores/`, body)).data,
  updateAssociation: async (productId: number, id: number, body: Partial<AssociationWrite>): Promise<ProductStore> =>
    (await apiClient.patch<ProductStore>(`/products/${productId}/stores/${id}/`, body)).data,
  deleteAssociation: async (productId: number, id: number): Promise<void> => {
    await apiClient.delete(`/products/${productId}/stores/${id}/`)
  },
}
