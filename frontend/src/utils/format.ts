export function formatDate(value?: string): string {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

export function formatMoney(value?: string | number): string {
  if (value === undefined || value === null || value === '') return '—'
  return `AED ${Number(value).toFixed(2)}`
}
