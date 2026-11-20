import { Clock3, Layers3, Mail, ShieldCheck, UserRound } from 'lucide-react'
import { useAuth } from '@/hooks/useAuth'
import { LoadingState } from '@/components/ui/feedback'
import { formatDate } from '@/utils/format'

function initialsFor(user: { full_name?: string; first_name?: string; last_name?: string; username?: string }): string {
  const name = [user.full_name, [user.first_name, user.last_name].filter(Boolean).join(' ')].find(
    (value) => Boolean(value && value.trim()),
  )
  const words = (name || user.username || '').trim().split(/\s+/).filter(Boolean)
  if (words.length === 0) return '?'
  const letters = words.length === 1 ? words[0].slice(0, 1) : words[0].slice(0, 1) + words[words.length - 1].slice(0, 1)
  return letters.toUpperCase()
}

function ContourDetail() {
  return (
    <svg className="mt-account-contours" viewBox="0 0 320 184" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <g fill="none" stroke="rgba(213,241,226,.26)" strokeWidth="1.15" strokeLinecap="round">
        <path d="M326 -8 C 246 4, 214 44, 254 84 S 306 142, 232 192" />
        <path d="M326 12 C 236 24, 196 64, 238 104 S 290 162, 214 206" />
        <path d="M326 32 C 226 44, 180 84, 222 124 S 274 182, 198 222" />
        <path d="M326 52 C 216 64, 166 104, 208 144 S 258 202, 184 240" />
        <path d="M326 72 C 208 84, 154 124, 194 164 S 244 220, 172 258" />
      </g>
    </svg>
  )
}

function Field({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode
  label: string
  value: string
}) {
  return (
    <div className="mt-account-field">
      <span className="mt-account-field-icon" aria-hidden="true">{icon}</span>
      <span className="mt-account-field-text">
        <dt className="mt-account-field-label">{label}</dt>
        <dd className="mt-account-field-value">{value}</dd>
      </span>
    </div>
  )
}

export function AccountPage() {
  const { user } = useAuth()

  if (!user) return <LoadingState label="Loading account…" />

  const displayName = user.full_name || [user.first_name, user.last_name].filter(Boolean).join(' ') || user.username || ''
  const handle = user.username ? `@${user.username.replace(/^@+/, '')}` : ''
  const role = user.roles.join(', ') || 'Not provided'
  const active = user.is_active === true
  const statusLabel = active ? 'Active' : user.is_active === false ? 'Inactive' : 'Not provided'

  return (
    <div className="mt-account">
      <style>{`
        .mt-account {
          width: 100%;
          max-width: 1120px;
          margin-inline: auto;
          margin-top: 10px;
          box-sizing: border-box;
          container-type: inline-size;
        }
        .mt-account *, .mt-account *::before, .mt-account *::after { box-sizing: border-box; }

        .mt-account-banner {
          position: relative;
          isolation: isolate;
          display: flex;
          align-items: center;
          gap: 24px;
          width: 100%;
          min-height: 184px;
          padding: 32px;
          overflow: hidden;
          border-radius: 20px;
          background: linear-gradient(90deg, #103A2A 0%, #0A291D 100%);
          color: #FFFFFF;
        }
        .mt-account-contours {
          position: absolute;
          z-index: -1;
          top: 0;
          right: 0;
          height: 100%;
          width: 42%;
          pointer-events: none;
          -webkit-mask-image: linear-gradient(to right, transparent 0%, #000 60%);
          mask-image: linear-gradient(to right, transparent 0%, #000 60%);
        }
        .mt-account-initials {
          display: flex;
          flex: none;
          align-items: center;
          justify-content: center;
          width: 88px;
          height: 88px;
          border-radius: 22px;
          background: #D5F1E2;
          color: #0E3D28;
          font-size: 30px;
          font-weight: 700;
          letter-spacing: -.5px;
        }
        .mt-account-divider {
          flex: none;
          width: 1px;
          align-self: stretch;
          min-height: 96px;
          background: rgba(213,241,226,.28);
        }
        .mt-account-identity { min-width: 0; }
        .mt-account-name {
          margin: 0;
          font-size: 32px;
          font-weight: 680;
          line-height: 1.12;
          letter-spacing: -.6px;
          overflow-wrap: break-word;
        }
        .mt-account-handle {
          margin: 6px 0 0;
          font-size: 16px;
          color: #BFE4CE;
          overflow-wrap: anywhere;
        }

        .mt-account-grid {
          display: grid;
          grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr);
          align-items: stretch;
          gap: 20px;
          margin-top: 20px;
        }
        .mt-account-card {
          min-width: 0;
          padding: 24px;
          border: 1px solid var(--line, #E8E5E0);
          border-radius: 20px;
          background: var(--card, #FFFFFF);
          box-shadow: var(--card-shadow, 0 4px 18px rgba(25,35,28,.06));
        }
        .mt-account-card-head {
          display: flex;
          align-items: center;
          gap: 10px;
          margin-bottom: 14px;
        }
        .mt-account-head-icon {
          display: flex;
          flex: none;
          align-items: center;
          justify-content: center;
          width: 36px;
          height: 36px;
          border-radius: 11px;
          background: var(--pos-bg, #E8F5EC);
          color: var(--pos, #1E8A5A);
        }
        .mt-account-card-title {
          margin: 0;
          font-size: 16px;
          font-weight: 650;
          color: var(--text-1, #1B1A17);
        }
        .mt-account-fields { margin: 0; }
        .mt-account-field {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 13px 0;
          border-bottom: 1px solid var(--line, #E8E5E0);
        }
        .mt-account-field-icon {
          display: flex;
          flex: none;
          align-items: center;
          justify-content: center;
          width: 32px;
          height: 32px;
          border-radius: 10px;
          background: var(--tile, #FAF8F5);
          color: var(--text-2, #6B665E);
        }
        .mt-account-field-text { display: flex; min-width: 0; flex: 1 1 auto; gap: 14px; }
        .mt-account-field-label {
          flex: 0 0 auto;
          font-size: 14px;
          color: var(--text-2, #6B665E);
        }
        .mt-account-field-value {
          margin: 0 0 0 auto;
          min-width: 0;
          text-align: right;
          font-size: 15px;
          font-weight: 500;
          color: var(--text-1, #1B1A17);
          overflow-wrap: anywhere;
        }
        .mt-account-note {
          display: flex;
          align-items: center;
          gap: 10px;
          margin-top: 18px;
          padding: 13px 14px;
          border-radius: 12px;
          background: #EFF7F0;
          color: #3B5C48;
          font-size: 13px;
          line-height: 1.4;
        }
        .mt-account-note svg { flex: none; }

        .mt-account-status-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          padding-bottom: 16px;
          border-bottom: 1px solid var(--line, #E8E5E0);
        }
        .mt-account-status-label { font-size: 14px; color: var(--text-2, #6B665E); }
        .mt-account-status-badge {
          display: inline-flex;
          align-items: center;
          gap: 7px;
          padding: 6px 12px;
          border-radius: 999px;
          font-size: 12.5px;
          font-weight: 600;
          color: var(--text-2, #6B665E);
          background: var(--inactive-bg, #EFEBE5);
        }
        .mt-account-status-badge[data-active="true"] {
          color: var(--pos, #1E8A5A);
          background: var(--pos-bg, #E8F5EC);
        }
        .mt-account-status-dot {
          width: 7px;
          height: 7px;
          border-radius: 50%;
          background: currentColor;
        }
        .mt-account-timeline { margin: 20px 0 0; padding: 0 0 0 26px; list-style: none; position: relative; }
        .mt-account-timeline::before {
          content: '';
          position: absolute;
          left: 5px;
          top: 6px;
          bottom: 12px;
          width: 1px;
          background: var(--line-input, rgba(45,30,15,.12));
        }
        .mt-account-event { position: relative; padding-bottom: 20px; }
        .mt-account-event:last-child { padding-bottom: 0; }
        .mt-account-marker {
          position: absolute;
          left: -26px;
          top: 4px;
          width: 11px;
          height: 11px;
          border-radius: 50%;
          border: 2px solid var(--text-3, #A19B91);
          background: var(--card, #FFFFFF);
        }
        .mt-account-marker[data-latest="true"] {
          border-color: var(--pos, #1E8A5A);
          background: var(--pos, #1E8A5A);
          box-shadow: 0 0 0 3px var(--pos-bg, #E8F5EC);
        }
        .mt-account-event-label { font-size: 14px; font-weight: 600; color: var(--text-1, #1B1A17); }
        .mt-account-event-date { margin-top: 3px; font-size: 13px; color: var(--text-2, #6B665E); }

        @container (max-width: 760px) {
          .mt-account-grid { grid-template-columns: minmax(0, 1fr); }
        }
        @container (max-width: 520px) {
          .mt-account-banner { padding: 20px; gap: 14px; min-height: 150px; }
          .mt-account-contours { opacity: .35; width: 34%; }
          .mt-account-initials { width: 60px; height: 60px; border-radius: 16px; font-size: 22px; }
          .mt-account-divider { display: none; }
          .mt-account-name { font-size: 24px; letter-spacing: -.3px; }
          .mt-account-handle { font-size: 14px; margin-top: 4px; }
          .mt-account-grid { gap: 14px; margin-top: 14px; }
          .mt-account-card { padding: 18px; }
          .mt-account-field { align-items: flex-start; gap: 10px; padding: 12px 0; }
          .mt-account-field-text { flex-direction: column; gap: 2px; }
          .mt-account-field-value { margin-left: 0; text-align: left; }
          .mt-account-note { align-items: flex-start; }
        }
        @container (max-width: 360px) {
          .mt-account-banner { flex-direction: column; align-items: flex-start; gap: 12px; }
          .mt-account-identity { width: 100%; }
        }
      `}</style>

      <section className="mt-account-banner" aria-label="Account identity">
        <ContourDetail />
        <span className="mt-account-initials" aria-hidden="true">{initialsFor(user)}</span>
        <span className="mt-account-divider" aria-hidden="true" />
        <div className="mt-account-identity">
          <p className="mt-account-name" aria-label="Full name">{displayName || 'Not provided'}</p>
          {handle && <p className="mt-account-handle" aria-label="Username">{handle}</p>}
        </div>
      </section>

      <div className="mt-account-grid">
        <section className="mt-account-card" aria-labelledby="account-details-title">
          <div className="mt-account-card-head">
            <span className="mt-account-head-icon"><UserRound className="h-[18px] w-[18px]" strokeWidth={1.8} aria-hidden="true" /></span>
            <h2 className="mt-account-card-title" id="account-details-title">Account details</h2>
          </div>
          <dl className="mt-account-fields">
            <Field icon={<Mail className="h-[16px] w-[16px]" strokeWidth={1.8} />} label="Email address" value={user.email || 'Not provided'} />
            <Field icon={<Layers3 className="h-[16px] w-[16px]" strokeWidth={1.8} />} label="Assigned role" value={role} />
          </dl>
          <p className="mt-account-note">
            <ShieldCheck className="h-[16px] w-[16px]" strokeWidth={1.8} aria-hidden="true" />
            Role and status are managed by an administrator.
          </p>
        </section>

        <section className="mt-account-card" aria-labelledby="account-history-title">
          <div className="mt-account-card-head">
            <span className="mt-account-head-icon"><Clock3 className="h-[18px] w-[18px]" strokeWidth={1.8} aria-hidden="true" /></span>
            <h2 className="mt-account-card-title" id="account-history-title">Account history</h2>
          </div>
          <div className="mt-account-status-row">
            <span className="mt-account-status-label">Account status</span>
            <span className="mt-account-status-badge" data-active={active}>
              <span className="mt-account-status-dot" aria-hidden="true" />
              {statusLabel}
            </span>
          </div>
          <ol className="mt-account-timeline">
            <li className="mt-account-event">
              <span className="mt-account-marker" data-latest="true" aria-hidden="true" />
              <p className="mt-account-event-label">Last updated</p>
              <p className="mt-account-event-date">{formatDate(user.updated_at)}</p>
            </li>
            <li className="mt-account-event">
              <span className="mt-account-marker" aria-hidden="true" />
              <p className="mt-account-event-label">Created</p>
              <p className="mt-account-event-date">{formatDate(user.date_joined)}</p>
            </li>
          </ol>
        </section>
      </div>
    </div>
  )
}
