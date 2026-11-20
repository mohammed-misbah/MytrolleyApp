import { useCallback, useEffect, useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Pencil, Trash2, Plus } from 'lucide-react'
import { toast } from 'sonner'
import type { Category } from '@/types'
import { catalogService } from '@/services/catalogService'
import { toError } from '@/services/apiClient'
import { serverErrorMessage } from '@/utils/formErrors'
import { Button } from '@/components/ui/button'
import { Field, Input, Textarea } from '@/components/ui/field'
import { Dialog, ConfirmDialog } from '@/components/ui/overlay'
import { EmptyState, ErrorState, ListSkeleton } from '@/components/ui/feedback'
import { categorySchema, type CategoryValues } from '@/schemas'

export function CategoriesPage() {
  const [items, setItems] = useState<Category[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Category | null>(null)
  const [toDelete, setToDelete] = useState<Category | null>(null)
  const [busy, setBusy] = useState(false)

  const { register, handleSubmit, reset, formState: { errors } } = useForm<CategoryValues>({
    resolver: zodResolver(categorySchema),
    defaultValues: { name: '', description: '' },
  })

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      setItems(await catalogService.listCategories())
    } catch (err) {
      setError(toError(err).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const openForm = (item?: Category) => {
    setEditing(item ?? null)
    reset(item ? { name: item.name, description: item.description } : { name: '', description: '' })
    setOpen(true)
  }

  const save = async (values: CategoryValues) => {
    setBusy(true)
    try {
      if (editing) {
        await catalogService.updateCategory(editing.id, values)
        toast.success('Category updated.')
      } else {
        await catalogService.createCategory(values)
        toast.success('Category created.')
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
      await catalogService.deleteCategory(toDelete.id)
      toast.success('Category deleted.')
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
          <h2 className="text-xl font-semibold text-ink">Categories</h2>
          <p className="text-sm text-subtle">Organise products into categories.</p>
        </div>
        <Button onClick={() => openForm()}><Plus className="h-4 w-4" /> Add category</Button>
      </div>

      <div className="overflow-hidden rounded-card border border-line bg-white shadow-card">
        {loading ? <div className="p-4"><ListSkeleton rows={5} /></div> : error ? <ErrorState message={error} onRetry={() => void load()} /> : items.length === 0 ? (
          <EmptyState title="No categories" description="Create a category to organise products." />
        ) : (
          <table className="w-full text-left text-sm">
            <thead className="text-[11px] uppercase tracking-wide text-subtle">
              <tr><th className="px-5 py-3 font-semibold">Name</th><th className="px-5 py-3 font-semibold">Slug</th><th className="px-5 py-3 font-semibold">Products</th><th className="px-5 py-3 font-semibold">Status</th><th className="px-5 py-3 text-right font-semibold">Actions</th></tr>
            </thead>
            <tbody className="divide-y divide-line">
              {items.map((c) => (
                <tr key={c.id} className="hover:bg-[var(--tile)]">
                  <td className="px-5 py-3 font-medium text-ink">{c.name}</td>
                  <td className="px-5 py-3 text-subtle">{c.slug}</td>
                  <td className="px-5 py-3 tabular-nums text-subtle">{c.product_count ?? 0}</td>
                  <td className="px-5 py-3"><span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${c.is_active ? 'bg-[var(--pos-bg)] text-[var(--pos)]' : 'bg-muted text-subtle'}`}>{c.is_active ? 'Active' : 'Inactive'}</span></td>
                  <td className="px-5 py-3 text-right">
                    <Button variant="ghost" size="icon" onClick={() => openForm(c)} title="Edit"><Pencil className="h-4 w-4" /></Button>
                    <Button variant="ghost" size="icon" onClick={() => setToDelete(c)} title="Delete"><Trash2 className="h-4 w-4 text-[var(--danger)]" /></Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <Dialog open={open} onOpenChange={setOpen} title={editing ? 'Edit category' : 'New category'}>
        <form onSubmit={handleSubmit(save)} className="space-y-4">
          <Field label="Name" error={errors.name?.message}><Input {...register('name')} /></Field>
          <Field label="Description"><Textarea {...register('description')} /></Field>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={busy}>Save</Button>
          </div>
        </form>
      </Dialog>
      <ConfirmDialog
        open={Boolean(toDelete)}
        onOpenChange={(o) => !o && setToDelete(null)}
        title="Delete category?"
        description={`"${toDelete?.name ?? ''}" will be removed if it has no products.`}
        onConfirm={() => void remove()}
        loading={busy}
      />
    </div>
  )
}
