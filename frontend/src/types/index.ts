export interface User {
  id: number
  username: string
  email: string
  first_name: string
  last_name: string
  full_name: string
  is_active: boolean
  is_staff: boolean
  date_joined?: string
  updated_at?: string
  roles: string[]
  permissions: string[]
}

export interface LoginResponse {
  access: string
  token_type: string
  expires_in: number
  refresh_expires_in: number
  user: User
}

export interface ApiErrorShape {
  code: string
  message: string
  fields: Record<string, string[]>
  request_id: string
}

export interface Category {
  id: number
  name: string
  slug: string
  description: string
  parent: number | null
  is_active: boolean
  created_at: string
  updated_at: string
  children?: Category[]
  product_count?: number
}

export interface Store {
  id: number
  name: string
  code: string
  description: string
  address: string
  is_active: boolean
  created_at: string
  updated_at: string
  product_count?: number
}

export interface DashboardSummary {
  products: { total: number; active: number; inactive: number }
  categories: number
  stores: number
  recent_products: ProductListItem[]
  creation_series: Array<{ date: string; count: number }>
  store_availability: Array<{
    id: number
    name: string
    code: string
    description: string
    address: string
    is_active: boolean
    created_at: string
    updated_at: string
    product_count: number
    out_of_stock: number
  }>
}

export interface ProductAttribute {
  id: number
  name: string
  value: string
  created_at?: string
  updated_at?: string
}

export interface ProductImage {
  id: number
  image: string
  image_url: string
  alt_text: string
  display_order: number
  is_primary: boolean
  created_at?: string
  updated_at?: string
}

export interface ProductStore {
  id: number
  store: Store
  store_id?: number
  price: string
  quantity: number
  is_available: boolean
  created_at?: string
  updated_at?: string
}

export interface ProductListItem {
  id: number
  name: string
  slug: string
  description: string
  category: string
  is_active: boolean
  created_at: string
  updated_at: string
  primary_image: ProductImage | null
  store_price: ProductStore | null
}

export interface ProductDetail {
  id: number
  name: string
  slug: string
  description: string
  category: Category
  category_id?: number
  is_active: boolean
  created_at: string
  updated_at: string
  attributes: ProductAttribute[]
  images: ProductImage[]
  store_associations: ProductStore[]
}

export interface ProductFilters {
  search?: string
  category?: number
  store?: number
  is_active?: boolean
  is_available?: boolean
  min_price?: string
  max_price?: string
  ordering?: string
  page?: number
  page_size?: number
}

export interface Paginated<T> {
  count: number
  page: number
  page_size: number
  total_pages: number
  results: T[]
}

export interface CategoryWrite {
  name: string
  description?: string
  parent?: number | null
  is_active?: boolean
}

export interface StoreWrite {
  name: string
  code: string
  description?: string
  address?: string
  is_active?: boolean
}

export interface ProductWrite {
  name: string
  description?: string
  category_id: number
  is_active?: boolean
}

export interface AssociationWrite {
  store_id: number
  price: string
  quantity: number
  is_available: boolean
}

export interface AttributeWrite {
  name: string
  value: string
}
