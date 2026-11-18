import axios from 'axios'
import { apiClient, multipartHeaders } from './apiClient'
import type {
  AssociationWrite,
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

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

function paramsFrom(filters: ProductFilters): Record<string, string | number | boolean> {
  const params: Record<string, string | number | boolean> = {}
  const entries = Object.entries(filters).filter(([, v]) => v !== undefined && v !== '' && v !== null)
  for (const [key, value] of entries) params[key] = value as string | number | boolean
  return params
}

export const catalogService = {
  // Categories
  listCategories: async (): Promise<Category[]> => (await apiClient.get<Category[]>('/categories/')).data,
  getCategory: async (id: number): Promise<Category> => (await apiClient.get<Category>(`/categories/${id}/`)).data,
  createCategory: async (body: CategoryWrite): Promise<Category> =>
    (await apiClient.post<Category>('/categories/', body)).data,
  updateCategory: async (id: number, body: Partial<CategoryWrite>): Promise<Category> =>
    (await apiClient.patch<Category>(`/categories/${id}/`, body)).data,
  deleteCategory: async (id: number): Promise<void> => {
    await apiClient.delete(`/categories/${id}/`)
  },

  // Stores
  listStores: async (): Promise<Store[]> => (await apiClient.get<Store[]>('/stores/')).data,
  getStore: async (id: number): Promise<Store> => (await apiClient.get<Store>(`/stores/${id}/`)).data,
  createStore: async (body: StoreWrite): Promise<Store> => (await apiClient.post<Store>('/stores/', body)).data,
  updateStore: async (id: number, body: Partial<StoreWrite>): Promise<Store> =>
    (await apiClient.patch<Store>(`/stores/${id}/`, body)).data,
  deleteStore: async (id: number): Promise<void> => {
    await apiClient.delete(`/stores/${id}/`)
  },

  // Products
  listProducts: async (filters: ProductFilters): Promise<Paginated<ProductListItem>> =>
    (await apiClient.get<Paginated<ProductListItem>>('/products/', { params: paramsFrom(filters) })).data,
  getProduct: async (id: number): Promise<ProductDetail> =>
    (await apiClient.get<ProductDetail>(`/products/${id}/`)).data,
  createProduct: async (body: ProductWrite): Promise<ProductDetail> =>
    (await apiClient.post<ProductDetail>('/products/', body)).data,
  updateProduct: async (id: number, body: Partial<ProductWrite>): Promise<ProductDetail> =>
    (await apiClient.patch<ProductDetail>(`/products/${id}/`, body)).data,
  deleteProduct: async (id: number): Promise<void> => {
    await apiClient.delete(`/products/${id}/`)
  },

  // Attributes
  listAttributes: async (productId: number): Promise<ProductAttribute[]> =>
    (await apiClient.get<ProductAttribute[]>(`/products/${productId}/attributes/`)).data,
  createAttribute: async (productId: number, body: AttributeWrite): Promise<ProductAttribute> =>
    (await apiClient.post<ProductAttribute>(`/products/${productId}/attributes/`, body)).data,
  updateAttribute: async (productId: number, id: number, body: Partial<AttributeWrite>): Promise<ProductAttribute> =>
    (await apiClient.patch<ProductAttribute>(`/products/${productId}/attributes/${id}/`, body)).data,
  deleteAttribute: async (productId: number, id: number): Promise<void> => {
    await apiClient.delete(`/products/${productId}/attributes/${id}/`)
  },

  // Images (multipart)
  listImages: async (productId: number): Promise<ProductImage[]> =>
    (await apiClient.get<ProductImage[]>(`/products/${productId}/images/`)).data,
  uploadImage: async (productId: number, file: File, meta?: Partial<Pick<ProductImage, 'alt_text' | 'display_order' | 'is_primary'>>): Promise<ProductImage> => {
    const form = new FormData()
    form.append('image', file)
    if (meta?.alt_text) form.append('alt_text', meta.alt_text)
    if (meta?.display_order !== undefined) form.append('display_order', String(meta.display_order))
    if (meta?.is_primary !== undefined) form.append('is_primary', String(meta.is_primary))
    const { data } = await axios.post<ProductImage>(
      `${BASE_URL}/products/${productId}/images/`,
      form,
      { headers: { ...multipartHeaders(), 'Content-Type': 'multipart/form-data' } },
    )
    return data
  },
  updateImage: async (productId: number, id: number, meta: Partial<Pick<ProductImage, 'alt_text' | 'display_order' | 'is_primary'>>): Promise<ProductImage> => {
    const form = new FormData()
    if (meta.alt_text !== undefined) form.append('alt_text', meta.alt_text)
    if (meta.display_order !== undefined) form.append('display_order', String(meta.display_order))
    if (meta.is_primary !== undefined) form.append('is_primary', String(meta.is_primary))
    const { data } = await axios.patch<ProductImage>(
      `${BASE_URL}/products/${productId}/images/${id}/`,
      form,
      { headers: { ...multipartHeaders(), 'Content-Type': 'multipart/form-data' } },
    )
    return data
  },
  deleteImage: async (productId: number, id: number): Promise<void> => {
    await apiClient.delete(`/products/${productId}/images/${id}/`)
  },

  // Product-store associations
  listAssociations: async (productId: number): Promise<ProductStore[]> =>
    (await apiClient.get<ProductStore[]>(`/products/${productId}/stores/`)).data,
  createAssociation: async (productId: number, body: AssociationWrite): Promise<ProductStore> =>
    (await apiClient.post<ProductStore>(`/products/${productId}/stores/`, body)).data,
  updateAssociation: async (productId: number, id: number, body: Partial<AssociationWrite>): Promise<ProductStore> =>
    (await apiClient.patch<ProductStore>(`/products/${productId}/stores/${id}/`, body)).data,
  deleteAssociation: async (productId: number, id: number): Promise<void> => {
    await apiClient.delete(`/products/${productId}/stores/${id}/`)
  },
}
