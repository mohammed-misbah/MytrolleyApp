# MY Trolley — Frontend Design Blueprint (Stage 2)

**Goal (in my own words):** build a premium React administration platform for
product/category/store/inventory management, inside the existing `frontend/`
folder only, using the supplied logo as the brand source of truth, the five
screenshots as visual direction, and the existing Django REST API as the sole
data source. The smallest change that meets Stage 1/2 is an inspection report
plus this blueprint (documents and reference images only). No application source
code is written until this blueprint is approved.

**Status:** Stage 1 complete, Stage 2 blueprint awaiting approval.

---

## 1. Stage 1 inspection findings

| Item | Finding |
|---|---|
| `frontend/` | Contains only `.gitkeep` — no existing React/Vite setup to preserve. |
| Root | `backend/`, `docs/`, `frontend/`, README, .gitignore, pstack skills. |
| Dependencies | None installed in `frontend/`; packages must be installed inside `frontend/` only. |
| Assessment document | No standalone assessment/PDF/DOCX file exists in the repository. Authoritative requirements are the supplied milestone prompts; backend IDs R-01…R-27 are in `docs/requirements-traceability.md`. |
| Backend API | 29 protected OpenAPI operations: auth (login/logout/me), categories CRUD, stores CRUD, products CRUD + search, attributes CRUD, images CRUD, product-store CRUD. Refresh is intentionally hidden from schema. |
| Auth | `POST /login/` returns Bearer access token in JSON; refresh cookie HttpOnly; logout revokes all sessions. `403` for missing business permission. |
| Permissions | `accounts.manage_catalog` held by Administrator and DataEntry; default-deny; no public catalog endpoints. |
| CORS | No CORS package/config — same-origin deployment required. |
| Media | `MEDIA_URL='/'`, no media URL patterns; `image_url` resolves to paths such as `/products/4/images/x.png` that Django currently does **not** serve. |
| Upload limits | `DATA_UPLOAD_MAX_MEMORY_SIZE` / `FILE_UPLOAD_MAX_MEMORY_SIZE` = 262 144 bytes; max 10 files; JSON max body configured. |
| URL style | `APPEND_SLASH=False` — exact trailing-slash URLs required. |
| Backend gaps | (a) media serving for uploaded images; (b) no category/product `search`/pagination params on category/store endpoints; (c) product list returns `store_price` only when `?store=` is supplied; (d) duplicate product names allowed (intentional, slug-unique); (e) `primary_image` falls back to first image when none is flagged primary. |

**Decision required before implementation (Stage 3+):**
1. Approve the **Vite dev proxy** approach: Vite on `127.0.0.1:5173` proxies `/api`
   to `127.0.0.1:8000`; same hostname means cookies (Path `/api/v1/auth/`) work
   in development without backend changes.
2. Decide whether image URLs must display in the browser. If yes, a backend
   change (media URL patterns / MEDIA_URL) is required — **outside `frontend/`**,
   so it needs explicit approval before any work.
3. Accept that category/store lists have no server-side search/pagination; the
   frontend will not fake them.

---

## 2. MY Trolley brand system (derived from `logo.png`)

Pixels sampled from the supplied logo (not guessed):

| Token | Value | Use |
|---|---|---|
| `brand.forest` | `#273F2F` | Sidebar, dark hero band, primary buttons, active nav |
| `brand.forestDeep` | `#1E3225` | Hover/pressed states, dark section background |
| `brand.lime` | `#ACD83D` | Primary accent, metric highlights, focus rings, lime CTA |
| `brand.limeSoft` | `#E8F5CC` | Tinted surfaces, active filter chips |
| `brand.red` | `#E61F26` | Rare warnings/errors only (logo wheels reference) |
| `neutral.white` | `#FFFFFF` | Cards, table surfaces, text on dark |
| `neutral.canvas` | `#F5F7F4` | App background (user-specified soft background) |
| `neutral.surfaceMuted` | `#F0F3EE` | Table header, striped rows |
| `text.primary` | `#1E2A22` | Main text |
| `text.secondary` | `#5E6B62` | Muted/secondary text |
| `border.subtle` | `#E2E8E1` | Dividers, table borders |

Usage rule: dark forest + white dominate; lime is an accent (≤10% of a screen);
red appears only in genuine error/destructive contexts. No purple, pink or
fitness/wallet colours from the references.

**Logo usage:** `frontend/src/assets/logo.png` (copy of `design-references/logo.png`)
rendered unmodified in sidebar header and login. No text-based replacement.

---

## 3. Typography, spacing and shape

- **Font:** Inter (or system UI fallback) — professional, neutral, excellent
  tabular numerals for tables and metrics.
- **Scale:** 11/12 (labels), 13 (secondary), 14 (body), 16 (subtitle), 20
  (section), 28/32 (page title), 36–40 (hero metric).
- **Weights:** 400 regular, 500 medium, 600 semibold, 700 bold (headings).
- **Line height:** 1.45 body, 1.2 headings; tabular numerals for prices/quantity.
- **Spacing scale (px):** 4, 8, 12, 16, 20, 24, 32, 40, 48, 64.
- **Radius:** 6 controls, 10 cards, 14 modals/drawers, 999 pills/badges.
- **Shadows:** subtle `0 1px 2px rgba(20,40,25,.05)`, medium
  `0 6px 20px rgba(20,40,25,.08)` for floating elements only.
- **Borders:** 1px `border.subtle`; no heavy outlines.

---

## 4. Component system (`src/components/ui`)

Button (primary forest / lime accent / outline / ghost / destructive), Input,
Select, Textarea, Checkbox, Badge/StatusPill, Card, Dialog, Drawer, ConfirmDialog,
Toast, Skeleton, EmptyState, ErrorState with Retry, Pagination, SearchInput,
DataTable primitives, Tabs, Tooltip. All tokens come from `src/styles/tokens.css`;
no page-level colour literals. shadcn/ui primitives where useful, themed to the
tokens above.

---

## 5. Layout and navigation (Reference 3)

- Desktop: fixed 240px sidebar, collapsible to 72px (icons only); content area
  with 24px padding and 1180px max width where appropriate.
- Sidebar: logo header, group "WORKSPACE" → Dashboard, Products, Categories,
  Stores, Product Attributes; group "ACCOUNT" → Logout. Active item = filled
  forest pill, white text/icon. Hover = lime-tinted background.
- Top header: page title/breadcrumb, user menu (name/role from `/auth/me/`),
  logout. Mobile: hamburger opens slide-over drawer with the same nav.

---

## 6. Dashboard (References 1 + 2 combined)

- Forest-green hero band: greeting with real user name/role, compact and
  distinctive, not photo-based.
- Row of four compact metric cards (Ref 1): Total Products, Active Products,
  Categories, Stores — large numerals, small labels, subtle lime icon squares.
- Secondary section (Ref 2 composition): white card with "Recent Products"
  (top 5 by `-created_at`) and a dark forest panel with "Store Inventory" —
  select a store and show product count with `is_available=true`.
- Optional status tiles computed from real counts; no wallet/order/fitness data.
- Empty/error/loading states for every card.

---

## 7. Product listing table (Reference 5 → table)

Desktop columns: **Product image** (small thumbnail), **Product name** +
secondary slug/ID, **Category**, **Attributes** (first 2–3 `name: value`
chips), **Associated stores** (count or first two codes), **Status** (Active /
Inactive pill; availability shown in drawer), **Actions** (View, Edit, Delete
icons with tooltips).

- Search input + category select + store select + availability select + price
  range + sort select + page-size select, all mapped 1:1 to backend query params.
- Clean dividers, 64px rows, subtle hover, sticky header, footer pagination.
- **Store-specific data** appears in a details drawer opened from the row:
  "Store A — AED 15.0000 — Qty 300 — Available", etc. No global price column.
- Mobile (<768px): each row becomes a card with thumbnail, name, status and
  actions; drawer still shows store rows.

---

## 8. Product form / image management / store inventory layouts

- **Form:** two-column desktop grid. Left: Basic information (name, description,
  category), Attributes dynamic list. Right: Images panel (dropzone + preview
  grid with primary toggle, order, delete), Store pricing panel (repeatable rows:
  store select, price, quantity, availability). Sticky action bar with
  Cancel/Save; save disabled until valid.
- **Images:** previews follow Reference 4 (large image on white, name as caption).
  Client-side type/size check (≤262 144 bytes) before upload; server 400 shown
  inline. Primary toggle calls PATCH; one primary per product.
- **Store rows:** each row visually separated with store code badge; price and
  quantity clearly labelled "AED" and "Units"; duplicate store blocked locally
  and by backend 409. Editing one row never rewrites another.
- **Detail view:** read-only sections + image gallery + store table + attribute
  list, with an "Edit" action.

---

## 9. API integration plan

- `src/services/apiClient.ts`: Axios instance with `baseURL` from
  `VITE_API_BASE_URL`, Bearer interceptor, error-normalisation interceptor
  (error envelope `code`, `message`, `fields`, `request_id`).
- `src/services/authService.ts`, `catalogService.ts` (categories, products,
  stores, attributes, images, associations).
- `src/types/*.ts`: User, Category, Store, Product, ProductImage, Attribute,
  ProductStore, PaginatedProducts, ApiError.
- `src/schemas/*.ts`: Zod schemas for login, product, category, store, attribute,
  store-association, image validation.
- `src/hooks/useAuth.ts`, `useCatalog.ts`, `usePermissions.ts`.
- Environment: `frontend/.env.example` with `VITE_API_BASE_URL=/api/v1`; no
  credentials in source. `withCredentials` not required for same-origin.
- Refresh handling: access token in memory; on 401, attempt refresh via
  `POST /auth/refresh/` with `X-CSRFToken` read from `document.cookie`; if that
  fails, redirect to login. Never store refresh token in JS.

---

## 10. Responsive strategy

| Width | Shell | Product list | Forms | Drawers |
|---|---|---|---|---|
| ≥1280 | fixed sidebar + content | full table | 2 columns | right drawer 420px |
| 1024–1279 | fixed sidebar | full table (tighter padding) | 2 columns | right drawer |
| 768–1023 | collapsible rail | table with fewer columns | 1 column | full-width drawer |
| <768 | slide-over nav | stacked cards | 1 column | full-screen sheet |

---

## 11. Verification plan (Stage 3+)

- `npm run build`, `npx tsc --noEmit`, lint if configured.
- Run dev server; open each page in a browser tool, capture desktop + mobile
  screenshots, compare with references, fix issues, repeat.
- Exercise real API login, CRUD, filters, image upload, store rows; inspect
  network tab to confirm real backend data only.
- Complete `REQUIREMENTS_TRACEABILITY.md` status column with Verified evidence.

---

## 12. Principles applied (pstack)

- **poteto-mode:** in-your-own-words goal restatement; staged workflow; no source
  edits before approval; final reports with evidence.
- **architect:** ground → sketch → agree; this document is the design sketch
  awaiting the agree checkpoint.
- **principle-model-the-domain:** store-specific price/quantity modelled only as
  association rows; permissions from real backend claims.
- **principle-prove-it-works / test-behavior-not-implementation:** planned
  browser screenshots and real-API interaction checks, not source-code claims.
