import { z } from 'zod'

export const loginSchema = z.object({
  username: z.string().min(1, 'Username is required.'),
  password: z.string().min(1, 'Password is required.'),
})
export type LoginValues = z.infer<typeof loginSchema>

export const productSchema = z.object({
  name: z.string().trim().min(1, 'Product name is required.').max(200, 'Maximum 200 characters.'),
  description: z.string().optional(),
  category_id: z.number().int().positive('Select a category.'),
  is_active: z.boolean(),
})
export type ProductValues = z.infer<typeof productSchema>

export const categorySchema = z.object({
  name: z.string().trim().min(1, 'Category name is required.').max(100),
  description: z.string().optional(),
})
export type CategoryValues = z.infer<typeof categorySchema>

export const storeSchema = z.object({
  name: z.string().trim().min(1, 'Store name is required.').max(100),
  code: z.string().trim().min(1, 'Store code is required.').max(20),
  description: z.string().optional(),
  address: z.string().optional(),
})
export type StoreValues = z.infer<typeof storeSchema>

export const attributeSchema = z.object({
  name: z.string().trim().min(1, 'Attribute name is required.'),
  value: z.string().trim().min(1, 'Attribute value is required.'),
})
export type AttributeValues = z.infer<typeof attributeSchema>

export const associationSchema = z.object({
  store_id: z.number().int().positive('Select a store.'),
  price: z.string().regex(/^\d+(\.\d{1,4})?$/, 'Enter a valid non-negative price.').refine((v) => Number(v) >= 0, 'Price cannot be negative.'),
  quantity: z.number().int().min(0, 'Quantity cannot be negative.'),
  is_available: z.boolean(),
})
export type AssociationValues = z.infer<typeof associationSchema>
