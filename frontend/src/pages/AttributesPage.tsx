import { useEffect, useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Pencil, Trash2, Plus } from 'lucide-react'
import { toast } from 'sonner'
import type { ProductAttribute } from '@/types'
import { catalogService } from '@/services/catalogService'
import { applyServerErrors, serverErrorMessage } from '@/utils/formErrors'
import { Button } from '@/components/ui/button'
import { Field, Input, Select } from '@/components/ui/field'
import { Dialog, ConfirmDialog } from '@/components/ui/overlay'
import { EmptyState, ListSkeleton } from '@/components/ui/feedback'
import { attributeSchema, type AttributeValues } from '@/schemas'

export function AttributesPage() {
  const [products, setProducts] = useState<{ id: number; name: string }[]>([])
  const [selected, setSelected] = useState<number | ''>('')
  const [items, setItems] = useState<ProductAttribute[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<number | null>(null)
  const [toDelete, setToDelete] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)

  const { register, handleSubmit, reset, setError, formState: { errors } } = useForm<AttributeValues>({
    resolver: zodResolver(attributeSchema),
    defaultValues: { name: '', value: '' },
  })

  useEffect(() => {
    void catalogService.listProducts({ page_size: 100 }).then((r) =>
      setProducts(r.results.map((p) => ({ id: p.id, name: p.name }))),
    ).catch(() => undefined)
  }, [])

  const load = async (productId: number) => {
    setLoading(true)
    try {
      setItems(await catalogService.listAttributes(productId))
    } catch (err) {
      toast.error(serverErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (selected !== '') void load(Number(selected))
    else setItems([])
  }, [selected])

  const openForm = (item?: ProductAttribute) => {
    setEditing(item?.id ?? null)
    reset(item ? { name: item.name, value: item.value } : { name: '', value: '' })
    setOpen(true)
  }

  const save = async (values: AttributeValues) => {
    if (selected === '') return
    setBusy(true)
    try {
      if (editing) {
        await catalogService.updateAttribute(Number(selected), editing, values)
        toast.success('Attribute updated.')
      } else {
        await catalogService.createAttribute(Number(selected), values)
        toast.success('Attribute added.')
      }
      setOpen(false)
      await load(Number(selected))
    } catch (err) {
      applyServerErrors(err, setError)
      toast.error(serverErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const remove = async () => {
    if (selected === '' || toDelete === null) return
    setBusy(true)
    try {
      await catalogService.deleteAttribute(Number(selected), toDelete)
      toast.success('Attribute removed.')
      setToDelete(null)
      await load(Number(selected))
    } catch (err) {
      toast.error(serverErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold text-ink">Product attributes</h2>
        <p className="text-sm text-subtle">Manage flexible details such as brand, size, colour and weight.</p>
      </div>
      <div className="rounded-card border border-line bg-white p-5 shadow-card">
        <Field label="Select product">
          <Select value={selected} onChange={(e) => setSelected(e.target.value ? Number(e.target.value) : '')}>
            <option value="">Choose a product…</option>
            {products.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </Select>
        </Field>
      </div>

      <div className="overflow-hidden rounded-card border border-line bg-white shadow-card">
        {selected === '' ? (
          <EmptyState title="Select a product" description="Attributes are managed per product." />
        ) : loading ? (
          <div className="p-4"><ListSkeleton rows={5} /></div>
        ) : items.length === 0 ? (
          <EmptyState title="No attributes" description="Add flexible attributes for this product." />
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="text-[11px] uppercase tracking-wide text-subtle">
              <tr><th className="px-5 py-3 font-semibold">Name</th><th className="px-5 py-3 font-semibold">Value</th><th className="px-5 py-3 text-right font-semibold">Actions</th></tr>
            </thead>
            <tbody className="divide-y divide-line">
              {items.map((a) => (
                <tr key={a.id} className="hover:bg-[var(--tile)]">
                  <td className="px-5 py-3 font-medium text-ink">{a.name}</td>
                  <td className="px-5 py-3 text-subtle">{a.value}</td>
                  <td className="px-5 py-3 text-right">
                    <Button variant="ghost" size="icon" onClick={() => openForm(a)}><Pencil className="h-4 w-4" /></Button>
                    <Button variant="ghost" size="icon" onClick={() => setToDelete(a.id)}><Trash2 className="h-4 w-4 text-[var(--danger)]" /></Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {selected !== '' && (
        <Button onClick={() => openForm()}><Plus className="h-4 w-4" /> Add attribute</Button>
      )}

      <Dialog open={open} onOpenChange={setOpen} title={editing ? 'Edit attribute' : 'Add attribute'}>
        <form onSubmit={handleSubmit(save)} className="space-y-4">
          <Field label="Name" error={errors.name?.message}><Input {...register('name')} /></Field>
          <Field label="Value" error={errors.value?.message}><Input {...register('value')} /></Field>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={busy}>Save</Button>
          </div>
        </form>
      </Dialog>
      <ConfirmDialog
        open={toDelete !== null}
        onOpenChange={(o) => !o && setToDelete(null)}
        title="Delete attribute?"
        description="This attribute will be removed from the product."
        onConfirm={() => void remove()}
        loading={busy}
      />
    </div>
  )
}
