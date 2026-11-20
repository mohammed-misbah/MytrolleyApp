import { useCallback, useEffect, useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Pencil, Trash2, Plus } from 'lucide-react'
import { toast } from 'sonner'
import type { Store } from '@/types'
import { catalogService } from '@/services/catalogService'
import { toError } from '@/services/apiClient'
import { serverErrorMessage } from '@/utils/formErrors'
import { Button } from '@/components/ui/button'
import { Field, Input, Textarea } from '@/components/ui/field'
import { Dialog, ConfirmDialog } from '@/components/ui/overlay'
import { EmptyState, ErrorState, ListSkeleton } from '@/components/ui/feedback'
import { storeSchema, type StoreValues } from '@/schemas'

export function StoresPage() {
  const [items, setItems] = useState<Store[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Store | null>(null)
  const [toDelete, setToDelete] = useState<Store | null>(null)
  const [busy, setBusy] = useState(false)

  const { register, handleSubmit, reset, formState: { errors } } = useForm<StoreValues>({
    resolver: zodResolver(storeSchema),
    defaultValues: { name: '', code: '', description: '', address: '' },
  })

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setItems(await catalogService.listStores())
    } catch (err) {
      setError(toError(err).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const openForm = (item?: Store) => {
    setEditing(item ?? null)
    reset(item ? { name: item.name, code: item.code, description: item.description, address: item.address } : { name: '', code: '', description: '', address: '' })
    setOpen(true)
  }

  const save = async (values: StoreValues) => {
    setBusy(true)
    try {
      if (editing) {
        await catalogService.updateStore(editing.id, values)
        toast.success('Store updated.')
      } else {
        await catalogService.createStore(values)
        toast.success('Store created.')
      }
      setOpen(false)
      await load()
    } catch (err) {
      toast.error(serverErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  const remove = async () => {
    if (!toDelete) return
    setBusy(true)
    try {
      await catalogService.deleteStore(toDelete.id)
      toast.success('Store deleted.')
      setToDelete(null)
      await load()
    } catch (err) {
      toast.error(serverErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-ink">Stores</h2>
          <p className="text-sm text-subtle">Manage locations with independent product pricing.</p>
        </div>
        <Button onClick={() => openForm()}><Plus className="h-4 w-4" /> Add store</Button>
      </div>

      <div className="overflow-hidden rounded-card border border-line bg-white shadow-card">
        {loading ? <div className="p-4"><ListSkeleton rows={5} /></div> : error ? <ErrorState message={error} onRetry={() => void load()} /> : items.length === 0 ? (
          <EmptyState title="No stores" description="Add a store to start associating products." />
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="text-[11px] uppercase tracking-wide text-subtle">
              <tr><th className="px-5 py-3 font-semibold">Store</th><th className="px-5 py-3 font-semibold">Code</th><th className="px-5 py-3 font-semibold">Address</th><th className="px-5 py-3 font-semibold">Products</th><th className="px-5 py-3 text-right font-semibold">Actions</th></tr>
            </thead>
            <tbody className="divide-y divide-line">
              {items.map((s) => (
                <tr key={s.id} className="hover:bg-[var(--tile)]">
                  <td className="px-5 py-3 font-medium text-ink">{s.name}</td>
                  <td className="px-5 py-3"><span className="rounded-full bg-[var(--pos-bg)] px-2 py-1 text-[11px] font-semibold text-[var(--pos)]">{s.code}</span></td>
                  <td className="px-5 py-3 text-subtle">{s.address || '—'}</td>
                  <td className="px-5 py-3 tabular-nums text-subtle">{s.product_count ?? 0}</td>
                  <td className="px-5 py-3 text-right">
                    <Button variant="ghost" size="icon" onClick={() => openForm(s)} title="Edit"><Pencil className="h-4 w-4" /></Button>
                    <Button variant="ghost" size="icon" onClick={() => setToDelete(s)} title="Delete"><Trash2 className="h-4 w-4 text-[var(--danger)]" /></Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <Dialog open={open} onOpenChange={setOpen} title={editing ? 'Edit store' : 'New store'}>
        <form onSubmit={handleSubmit(save)} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Name" error={errors.name?.message}><Input {...register('name')} /></Field>
            <Field label="Code" error={errors.code?.message}><Input {...register('code')} /></Field>
          </div>
          <Field label="Description"><Textarea {...register('description')} /></Field>
          <Field label="Address"><Input {...register('address')} /></Field>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={busy}>Save</Button>
          </div>
        </form>
      </Dialog>
      <ConfirmDialog
        open={Boolean(toDelete)}
        onOpenChange={(o) => !o && setToDelete(null)}
        title="Delete store?"
        description="The store can only be deleted when no products are associated with it."
        onConfirm={() => void remove()}
        loading={busy}
      />
    </div>
  )
}
