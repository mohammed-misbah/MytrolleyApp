import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { zodResolver } from '@hookform/resolvers/zod'
import { Controller, useForm } from 'react-hook-form'
import { ImagePlus, Star, Trash2, Plus, ArrowLeft, Save } from 'lucide-react'
import { toast } from 'sonner'
import type { AttributeWrite, AssociationWrite, Category, Store } from '@/types'
import { catalogService } from '@/services/catalogService'
import { toError } from '@/services/apiClient'
import { applyServerErrors, serverErrorMessage } from '@/utils/formErrors'
import { Button } from '@/components/ui/button'
import { Field, Input, Select, Textarea } from '@/components/ui/field'
import { ConfirmDialog, Dialog } from '@/components/ui/overlay'
import { EmptyState, LoadingState } from '@/components/ui/feedback'
import { AppImage } from '@/components/ui/AppImage'
import { attributeSchema, associationSchema, productSchema, type AttributeValues, type AssociationValues, type ProductValues } from '@/schemas'
import { formatMoney } from '@/utils/format'

const MAX_BYTES = 1_048_576
const MAX_IMAGES = 10
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']

type DraftImage = {
  id?: number
  image_url: string
  alt_text: string
  is_primary: boolean
  file?: File
}
type DraftAttribute = { id?: number; name: string; value: string }
type DraftAssociation = {
  id?: number
  store: Store
  price: string
  quantity: number
  is_available: boolean
}

export function ProductFormPage() {
  const { id } = useParams()
  const productId = id ? Number(id) : null
  const navigate = useNavigate()
  const fileRef = useRef<HTMLInputElement>(null)

  const [categories, setCategories] = useState<Category[]>([])
  const [stores, setStores] = useState<Store[]>([])
  const [images, setImages] = useState<DraftImage[]>([])
  const [attributes, setAttributes] = useState<DraftAttribute[]>([])
  const [associations, setAssociations] = useState<DraftAssociation[]>([])
  const objectUrls = useRef<string[]>([])
  const [loading, setLoading] = useState(Boolean(productId))
  const [saving, setSaving] = useState(false)
  const [attributeOpen, setAttributeOpen] = useState(false)
  const [associationOpen, setAssociationOpen] = useState(false)
  const [editingAttribute, setEditingAttribute] = useState<number | null>(null)
  const [editingAssociation, setEditingAssociation] = useState<number | null>(null)
  const [deleteImage, setDeleteImage] = useState<DraftImage | null>(null)
  const [deleteAssociation, setDeleteAssociation] = useState<DraftAssociation | null>(null)

  const {
    register,
    control,
    handleSubmit,
    reset,
    setError,
    formState: { errors },
  } = useForm<ProductValues>({
    resolver: zodResolver(productSchema),
    defaultValues: { name: '', description: '', category_id: 0, is_active: true },
  })

  const load = useCallback(async () => {
    if (!productId) {
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const detail = await catalogService.getProduct(productId)
      setImages(detail.images)
      setAttributes(detail.attributes)
      setAssociations(detail.store_associations)
      reset({
        name: detail.name,
        description: detail.description,
        category_id: detail.category?.id ?? 0,
        is_active: detail.is_active,
      })
    } catch (err) {
      toast.error(serverErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }, [productId, reset])

  useEffect(() => {
    void load()
    void catalogService.listCategories().then(setCategories).catch(() => undefined)
    void catalogService.listStores().then(setStores).catch(() => undefined)
  }, [load])

  useEffect(() => () => objectUrls.current.forEach((url) => URL.revokeObjectURL(url)), [])

  const onSave = async (values: ProductValues) => {
    setSaving(true)
    try {
      if (productId) {
        await catalogService.updateProduct(productId, values)
        toast.success('Product updated.')
        await load()
      } else {
        const storeIds = associations.map((item) => item.store.id)
        const attributeNames = attributes.map((item) => item.name.trim().toLowerCase())
        if (images.length > MAX_IMAGES) {
          toast.error(`Upload at most ${MAX_IMAGES} images.`)
          return
        }
        if (new Set(storeIds).size !== storeIds.length) {
          toast.error('Each store can only be added once.')
          return
        }
        if (new Set(attributeNames).size !== attributeNames.length) {
          toast.error('Attribute names must be unique.')
          return
        }
        const form = new FormData()
        form.append('name', values.name)
        form.append('description', values.description || '')
        form.append('category_id', String(values.category_id))
        form.append('is_active', String(values.is_active))
        form.append(
          'attributes',
          JSON.stringify(attributes.map(({ name, value }) => ({ name, value }))),
        )
        form.append(
          'stores',
          JSON.stringify(
            associations.map((association) => ({
              store_id: association.store.id,
              price: association.price,
              quantity: association.quantity,
              is_available: association.is_available,
            })),
          ),
        )
        images.forEach((image) => {
          if (image.file) form.append('images', image.file)
        })
        const created = await catalogService.createProductWithRelations(form)
        objectUrls.current = []
        toast.success('Product created with images, attributes and store pricing.')
        navigate(`/products/${created.id}/edit`, { replace: true })
      }
    } catch (err) {
      const e = toError(err)
      applyServerErrors(e, setError)
      toast.error(serverErrorMessage(e))
    } finally {
      setSaving(false)
    }
  }

  const upload = async (files: FileList | null) => {
    if (!files?.length) return
    if (!productId) {
      if (images.length + files.length > MAX_IMAGES) {
        toast.error(`Upload at most ${MAX_IMAGES} images.`)
      } else {
        const drafts: DraftImage[] = []
        for (const file of Array.from(files)) {
          if (!ALLOWED_TYPES.includes(file.type)) {
            toast.error(`${file.name}: unsupported file type.`)
            continue
          }
          if (file.size > MAX_BYTES) {
            toast.error('File exceeds the 1 MB limit.')
            continue
          }
          const url = URL.createObjectURL(file)
          objectUrls.current.push(url)
          drafts.push({
            image_url: url,
            alt_text: file.name,
            is_primary: false,
            file,
          })
        }
        // Only the first image in the whole gallery is primary.
        drafts.forEach((draft, index) => {
          draft.is_primary = images.length === 0 && index === 0
        })
        setImages((prev) => [...prev, ...drafts])
        if (drafts.length) toast.success(`${drafts.length} image${drafts.length === 1 ? '' : 's'} added.`)
      }
      if (fileRef.current) fileRef.current.value = ''
      return
    }

    // Only one image may be primary, including across a multi-file upload.
    let hasPrimary = images.some((image) => image.is_primary)
    for (const file of Array.from(files)) {
      if (!ALLOWED_TYPES.includes(file.type)) {
        toast.error(`${file.name}: unsupported file type.`)
        continue
      }
      if (file.size > MAX_BYTES) {
        toast.error('File exceeds the 1 MB limit.')
        continue
      }
      try {
        const created = await catalogService.uploadImage(productId, file, { is_primary: !hasPrimary })
        setImages((prev) => [...prev, created])
        if (created.is_primary) hasPrimary = true
        toast.success('Image uploaded.')
      } catch (err) {
        toast.error(serverErrorMessage(err))
      }
    }
    if (fileRef.current) fileRef.current.value = ''
  }

  const makePrimary = async (image: DraftImage) => {
    if (!image.id) {
      setImages((prev) => prev.map((item) => ({ ...item, is_primary: item === image })))
      return
    }
    if (!productId) return
    try {
      const updated = await catalogService.updateImage(productId, image.id, { is_primary: true })
      setImages((prev) => prev.map((i) => ({ ...i, is_primary: i.id === updated.id ? true : false })))
      toast.success('Primary image updated.')
    } catch (err) {
      toast.error(serverErrorMessage(err))
    }
  }

  const confirmDeleteImage = async () => {
    if (!deleteImage) return
    if (!deleteImage.id) {
      URL.revokeObjectURL(deleteImage.image_url)
      objectUrls.current = objectUrls.current.filter((url) => url !== deleteImage.image_url)
      setImages((prev) => prev.filter((item) => item !== deleteImage))
      if (deleteImage.is_primary) {
        setImages((prev) => prev.map((item, index) => ({ ...item, is_primary: index === 0 })))
      }
      setDeleteImage(null)
      return
    }
    if (!productId) return
    try {
      await catalogService.deleteImage(productId, deleteImage.id)
      setImages((prev) => prev.filter((i) => i.id !== deleteImage.id))
      toast.success('Image deleted.')
      setDeleteImage(null)
    } catch (err) {
      toast.error(serverErrorMessage(err))
    }
  }

  const saveAttribute = async (values: AttributeValues) => {
    if (!productId) {
      if (editingAttribute) {
        setAttributes((prev) =>
          prev.map((item) =>
            item.id === editingAttribute ? { ...item, ...values } : item,
          ),
        )
      } else {
        setAttributes((prev) => [
          ...prev,
          { id: -(Date.now() + prev.length), name: values.name, value: values.value },
        ])
      }
      setAttributeOpen(false)
      setEditingAttribute(null)
      return
    }
    if (editingAttribute) {
      const updated = await catalogService.updateAttribute(productId, editingAttribute, values)
      setAttributes((prev) => prev.map((a) => (a.id === updated.id ? updated : a)))
      toast.success('Attribute updated.')
    } else {
      const created = await catalogService.createAttribute(productId, values as AttributeWrite)
      setAttributes((prev) => [...prev, created])
      toast.success('Attribute added.')
    }
    setAttributeOpen(false)
    setEditingAttribute(null)
  }

  const deleteAttributeRow = async (id: number) => {
    if (!productId) {
      setAttributes((prev) => prev.filter((item) => item.id !== id))
      return
    }
    try {
      await catalogService.deleteAttribute(productId, id)
      setAttributes((prev) => prev.filter((a) => a.id !== id))
      toast.success('Attribute removed.')
    } catch (err) {
      toast.error(serverErrorMessage(err))
    }
  }

  const saveAssociation = async (values: AssociationValues) => {
    const store = stores.find((item) => item.id === Number(values.store_id))
    if (!productId) {
      if (!store) {
        toast.error('Select a valid store.')
        return
      }
      const draft: DraftAssociation = {
        id: editingAssociation ?? -(Date.now() + associations.length),
        store,
        price: String(values.price),
        quantity: Number(values.quantity),
        is_available: Boolean(values.is_available),
      }
      setAssociations((prev) =>
        editingAssociation
          ? prev.map((item) => (item.id === editingAssociation ? draft : item))
          : [...prev, draft],
      )
      setAssociationOpen(false)
      setEditingAssociation(null)
      return
    }
    const payload: AssociationWrite = {
      store_id: Number(values.store_id),
      price: String(values.price),
      quantity: Number(values.quantity),
      is_available: Boolean(values.is_available),
    }
    if (editingAssociation) {
      const updated = await catalogService.updateAssociation(productId, editingAssociation, payload)
      setAssociations((prev) => prev.map((a) => (a.id === updated.id ? updated : a)))
      toast.success('Store association updated.')
    } else {
      const created = await catalogService.createAssociation(productId, payload)
      setAssociations((prev) => [...prev, created])
      toast.success('Store association added.')
    }
    setAssociationOpen(false)
    setEditingAssociation(null)
  }

  const confirmDeleteAssociation = async () => {
    if (!deleteAssociation) return
    if (!deleteAssociation.id || deleteAssociation.id < 0) {
      setAssociations((prev) => prev.filter((item) => item.id !== deleteAssociation.id))
      setDeleteAssociation(null)
      return
    }
    if (!productId) return
    try {
      await catalogService.deleteAssociation(productId, deleteAssociation.id)
      setAssociations((prev) => prev.filter((a) => a.id !== deleteAssociation.id))
      toast.success('Store association removed.')
      setDeleteAssociation(null)
    } catch (err) {
      toast.error(serverErrorMessage(err))
    }
  }

  if (loading) return <LoadingState label="Loading product…" />

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate('/products')} aria-label="Back">
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h2 className="text-xl font-semibold text-ink">{productId ? 'Edit product' : 'New product'}</h2>
          <p className="text-sm text-subtle">
            {productId ? 'Update details, images, attributes and store pricing.' : 'Add images, attributes and store pricing, then create everything in one step.'}
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit(onSave)} className="grid gap-5 xl:grid-cols-[1.2fr_1fr]">
        <div className="space-y-5">
          <section className="rounded-card border border-line bg-white p-5 shadow-card">
            <h3 className="mb-4 text-sm font-semibold text-ink">Basic information</h3>
            <div className="space-y-4">
              <Field label="Product name" error={errors.name?.message}>
                <Input placeholder="e.g. Samsung S27" {...register('name')} />
              </Field>
              <Field label="Description" error={errors.description?.message}>
                <Textarea placeholder="Describe the product…" {...register('description')} />
              </Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Category" error={errors.category_id?.message}>
                  <Select {...register('category_id', { valueAsNumber: true })}>
                    <option value={0}>Select a category</option>
                    {categories.map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </Select>
                </Field>
                <Field label="Status">
                  <Controller
                    name="is_active"
                    control={control}
                    render={({ field }) => (
                      <Select
                        name={field.name}
                        ref={field.ref}
                        value={field.value ? 'true' : 'false'}
                        onChange={(event) => field.onChange(event.target.value === 'true')}
                        onBlur={field.onBlur}
                      >
                        <option value="true">Active</option>
                        <option value="false">Inactive</option>
                      </Select>
                    )}
                  />
                </Field>
              </div>
            </div>
          </section>

          <section className="rounded-card border border-line bg-white p-5 shadow-card">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-ink">Attributes</h3>
              <Button type="button" size="sm" variant="outline" onClick={() => { setEditingAttribute(null); setAttributeOpen(true) }}>
                <Plus className="h-3.5 w-3.5" /> Add attribute
              </Button>
            </div>
            {attributes.length ? (
              <div className="divide-y divide-line">
                {attributes.map((a) => (
                  <div key={a.id ?? a.name} className="flex items-center justify-between py-2.5 text-sm">
                    <span><span className="font-medium">{a.name}</span>: {a.value}</span>
                    <div className="flex gap-1">
                      <Button type="button" variant="ghost" size="sm" onClick={() => { setEditingAttribute(a.id ?? null); setAttributeOpen(true) }}>Edit</Button>
                      <Button type="button" variant="ghost" size="icon" onClick={() => void deleteAttributeRow(a.id ?? 0)}>
                        <Trash2 className="h-4 w-4 text-[var(--danger)]" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No attributes" description="Add details such as brand, size, colour or weight." />
            )}
          </section>
        </div>

        <div className="space-y-5">
          <section className="rounded-card border border-line bg-white p-5 shadow-card">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-ink">Product images</h3>
              <Button type="button" size="sm" variant="outline" onClick={() => fileRef.current?.click()}>
                <ImagePlus className="h-3.5 w-3.5" /> Upload
              </Button>
              <input ref={fileRef} type="file" accept="image/*" multiple className="hidden" onChange={(e) => void upload(e.target.files)} />
            </div>
            {images.length ? (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                {images.map((image) => (
                  <div key={image.id ?? image.image_url} className="group relative overflow-hidden rounded-card border border-line bg-muted">
                    <AppImage src={image.image_url} alt={image.alt_text} productId={productId ?? undefined} imageId={image.id} className="aspect-square w-full object-cover" />
                    {image.is_primary && (
                      <span className="absolute left-2 top-2 rounded-full bg-lime px-2 py-0.5 text-[10px] font-semibold text-[var(--pos)]">Primary</span>
                    )}
                    <div className="flex items-center justify-between gap-1 p-1.5">
                      {image.is_primary ? (
                        <span className="text-[10px] text-subtle">Current primary</span>
                      ) : (
                        <Button type="button" size="sm" variant="ghost" className="h-6 px-1 text-[10px]" onClick={() => void makePrimary(image)}>
                          <Star className="h-3 w-3" /> Make primary
                        </Button>
                      )}
                      <Button type="button" size="icon" variant="ghost" className="h-6 w-6" onClick={() => setDeleteImage(image)}>
                        <Trash2 className="h-3.5 w-3.5 text-[var(--danger)]" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No images" description="Upload up to 10 images (max 1 MB each)." />
            )}
          </section>

          <section className="rounded-card border border-line bg-white p-5 shadow-card">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-ink">Store pricing & inventory</h3>
                <p className="text-xs text-subtle">Each store has its own price and quantity.</p>
              </div>
              <Button type="button" size="sm" variant="outline" onClick={() => { setEditingAssociation(null); setAssociationOpen(true) }}>
                <Plus className="h-3.5 w-3.5" /> Add store
              </Button>
            </div>
            {associations.length ? (
              <div className="space-y-2">
                {associations.map((a) => (
                  <div key={a.id ?? a.store.id} className="flex items-center justify-between rounded-control border border-line px-3 py-2.5">
                    <div>
                      <p className="text-sm font-medium text-ink">{a.store.name} <span className="text-xs text-subtle">({a.store.code})</span></p>
                      <p className="text-xs text-subtle">{formatMoney(a.price)} · Qty {a.quantity} · {a.is_available ? 'Available' : 'Unavailable'}</p>
                    </div>
                    <div className="flex gap-1">
                      <Button type="button" size="sm" variant="ghost" onClick={() => { setEditingAssociation(a.id ?? null); setAssociationOpen(true) }}>Edit</Button>
                      <Button type="button" size="icon" variant="ghost" onClick={() => setDeleteAssociation(a)}>
                        <Trash2 className="h-4 w-4 text-[var(--danger)]" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState title="No store associations" description="Add a store with its own price and available quantity." />
            )}
          </section>
        </div>

        <div className="xl:col-span-2">
          <div className="flex justify-end gap-2 border-t border-line pt-4">
            <Button type="button" variant="outline" onClick={() => navigate('/products')}>Cancel</Button>
            <Button type="submit" disabled={saving}>
              {saving ? 'Saving…' : <><Save className="h-4 w-4" /> {productId ? 'Save changes' : 'Create product'}</>}
            </Button>
          </div>
        </div>
      </form>

      <AttributeDialog
        open={attributeOpen}
        onOpenChange={setAttributeOpen}
        initial={attributes.find((a) => a.id === editingAttribute)}
        onSave={saveAttribute}
      />
      <AssociationDialog
        open={associationOpen}
        onOpenChange={setAssociationOpen}
        stores={stores}
        initial={associations.find((a) => a.id === editingAssociation)}
        onSave={saveAssociation}
      />
      <ConfirmDialog
        open={Boolean(deleteImage)}
        onOpenChange={(open) => !open && setDeleteImage(null)}
        title="Delete image?"
        description="This will permanently remove the uploaded image."
        onConfirm={() => void confirmDeleteImage()}
      />
      <ConfirmDialog
        open={Boolean(deleteAssociation)}
        onOpenChange={(open) => !open && setDeleteAssociation(null)}
        title="Remove store association?"
        description="Other stores and their pricing remain unchanged."
        onConfirm={() => void confirmDeleteAssociation()}
      />
    </div>
  )
}

function AttributeDialog({
  open,
  onOpenChange,
  initial,
  onSave,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  initial?: DraftAttribute
  onSave: (values: AttributeValues) => Promise<void>
}) {
  const { register, handleSubmit, reset, setError, formState: { errors } } = useForm<AttributeValues>({
    resolver: zodResolver(attributeSchema),
    defaultValues: { name: '', value: '' },
  })
  useEffect(() => {
    reset(initial ? { name: initial.name, value: initial.value } : { name: '', value: '' })
  }, [initial, reset])

  const submit = async (values: AttributeValues) => {
    try {
      await onSave(values)
    } catch (err) {
      applyServerErrors(err, setError)
      toast.error(serverErrorMessage(err))
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={initial ? 'Edit attribute' : 'Add attribute'}>
      <form onSubmit={handleSubmit(submit)} className="space-y-4">
        <Field label="Name" error={errors.name?.message}>
          <Input placeholder="e.g. Brand" {...register('name')} />
        </Field>
        <Field label="Value" error={errors.value?.message}>
          <Input placeholder="e.g. Samsung" {...register('value')} />
        </Field>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button type="submit">Save</Button>
        </div>
      </form>
    </Dialog>
  )
}

function AssociationDialog({
  open,
  onOpenChange,
  stores,
  initial,
  onSave,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  stores: Store[]
  initial?: DraftAssociation
  onSave: (values: AssociationValues) => Promise<void>
}) {
  const { register, handleSubmit, reset, setError, formState: { errors } } = useForm<AssociationValues>({
    resolver: zodResolver(associationSchema),
    defaultValues: { store_id: 0, price: '0', quantity: 0, is_available: true },
  })
  useEffect(() => {
    reset(
      initial
        ? { store_id: initial.store.id, price: initial.price, quantity: initial.quantity, is_available: initial.is_available }
        : { store_id: 0, price: '0', quantity: 0, is_available: true },
    )
  }, [initial, reset])

  const submit = async (values: AssociationValues) => {
    try {
      await onSave(values)
    } catch (err) {
      applyServerErrors(err, setError)
      toast.error(serverErrorMessage(err))
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={initial ? 'Edit store association' : 'Add store association'} description="Price and quantity apply only to this store.">
      <form onSubmit={handleSubmit(submit)} className="space-y-4">
        <Field label="Store" error={errors.store_id?.message}>
          <Select {...register('store_id', { valueAsNumber: true })} disabled={Boolean(initial?.id && initial.id > 0)}>
            <option value={0}>Select a store</option>
            {stores.map((s) => (
              <option key={s.id} value={s.id}>{s.name} ({s.code})</option>
            ))}
          </Select>
        </Field>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Price (AED)" error={errors.price?.message}>
            <Input step="0.01" type="number" min={0} {...register('price')} />
          </Field>
          <Field label="Available quantity" error={errors.quantity?.message}>
            <Input type="number" min={0} {...register('quantity', { valueAsNumber: true })} />
          </Field>
        </div>
        <label className="flex items-center gap-2 text-sm text-ink">
          <input type="checkbox" {...register('is_available')} className="h-4 w-4 accent-forest" />
          Available in this store
        </label>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button type="submit">Save</Button>
        </div>
      </form>
    </Dialog>
  )
}
