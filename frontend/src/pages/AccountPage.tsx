import { ShieldCheck, UserRound } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { LoadingState } from '@/components/ui/feedback'
import { formatDate } from '@/utils/format'

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-1 border-b border-line py-3 last:border-0 sm:flex-row sm:items-center sm:justify-between">
      <span className="text-xs font-semibold uppercase tracking-wide text-subtle">{label}</span>
      <span className="text-sm font-medium text-ink">{value || '—'}</span>
    </div>
  )
}

export function AccountPage() {
  const { user } = useAuth()

  if (!user) return <LoadingState label="Loading account…" />

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold text-ink">My Account</h2>
        <p className="text-sm text-subtle">Your account information from the authenticated session.</p>
      </div>

      <section className="max-w-2xl rounded-card border border-line bg-white p-5 shadow-card">
        <div className="mb-4 flex items-center gap-2">
          <span className="rounded-control bg-lime-soft p-2 text-forest">
            <UserRound className="h-4 w-4" />
          </span>
          <h3 className="text-sm font-semibold text-ink">Account information</h3>
        </div>
        <InfoRow label="Full name" value={user.full_name || user.username} />
        <InfoRow label="Username" value={user.username} />
        <InfoRow label="Email address" value={user.email} />
        <InfoRow label="Assigned role" value={user.roles.join(', ') || 'No role'} />
        <InfoRow label="Account status" value={user.is_active ? 'Active' : 'Inactive'} />
        <InfoRow label="Created" value={formatDate(user.date_joined)} />
        <InfoRow label="Last updated" value={formatDate(user.updated_at)} />
        <p className="mt-3 flex items-center gap-1.5 text-xs text-subtle">
          <ShieldCheck className="h-3.5 w-3.5" /> Role and status are managed by an administrator.
        </p>
      </section>
    </div>
  )
}
