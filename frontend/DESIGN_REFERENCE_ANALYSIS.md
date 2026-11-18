# MY Trolley — Design Reference Analysis (Stage 2)

All six supplied images were inspected individually and copied into
`frontend/design-references/`. They are visual references only — no business
functionality is copied from them.

---

## Logo — `logo.png`

**Observed:** Dark forest-green square field. Centred white wordmark "MY Rolley".
The letter "T" is replaced by a lime-green trolley/cart glyph with two small red
circles (wheels) underneath. Small lime tagline "Everything for you." under the
wordmark.

**Reuse:**
- Preserve the image exactly as supplied; do not redraw the wordmark or the
  trolley glyph as text/CSS.
- Use it unmodified in the sidebar header and the login screen.
- Use the forest green as the sidebar/header surface and the lime green as the
  primary accent.

**Adapt:**
- Scale it proportionally; provide a compact version by resizing the whole image
  (never by cropping or stretching the glyph).
- Place it on dark surfaces where it blends into its own background.

**Avoid:**
- Recreating the logo with typography, recolouring it, adding effects, or
  placing it on a light card where its dark background box looks accidental.
- Treating the red wheels as a major UI colour.

---

## Reference 1 — `reference-1-dashboard-stat-cards.png`

**Observed:** Laptop screen showing a light dashboard with colourful compact
statistic cards (purple, white), small coloured square icons, labels such as
"Total Brands", "Total Categories", "Total Orders", order-status tiles
("Pending", "Processed", "On The Way", "PickUp", "Cancelled", "Completed"), an
"Admin Wallet" column with stacked white rows, and a purple "All Orders" button.
Dense but well organised; strong hierarchy via colour blocks and large numbers.

**Reuse:**
- Compact metric-card grid with large numerals and small labels.
- Status tiles with small coloured icon squares.
- A secondary stacked-list card for detailed information.

**Adapt:**
- Translate every metric to real catalog data: Total Products, Active Products,
  Categories, Stores, Store Associations, Low/Out-of-stock, Recent Products.
- Replace the purple wallet palette with MY Trolley forest green / lime green.
- Use the status-tile idea for `is_active` / `is_available` counts, not for
  invented order or finance data.

**Avoid:**
- Copying "Total Orders", "Admin Wallet", "Earnings", "Withdrawal" and similar
  finance/order metrics — the backend has no such data.
- Copying the purple/lavender colour scheme.

---

## Reference 2 — `reference-2-dashboard-premium.png`

**Observed:** Large dark hero area on the left with a photographic subject,
white metric cards on the right with sparkline-style mini charts, a pink
highlight card with a circular 34% indicator, and a lower dark section with lime
green area charts and a circular progress graphic. Strong contrast between dark
and white surfaces, generous whitespace, premium composition.

**Reuse:**
- Dark hero/summary band paired with floating white metric cards.
- Balanced white/dark surface composition and generous spacing.
- Small inline trend-style visuals and circular indicators where real data
  supports them.

**Adapt:**
- Hero becomes a forest-green branded welcome/summary band with the real user's
  name and role from `/auth/me/`, not a photographic wellness subject.
- Replace fake health metrics with catalog metrics derived from real API data.
- If charts are used at all, derive them from real counts (e.g. products by
  category, stock by store); otherwise omit charts rather than inventing them.

**Avoid:**
- Copying the wellness/medical imagery, the pink gradient card, sleep/heart-rate
  metrics, and the lime "Program" chart labels — none belong to this product.

---

## Reference 3 — `reference-3-sidebar-navigation.png`

**Observed:** Narrow white vertical sidebar on a mobile device. Brand mark at
top. Active item "Overview" is a filled dark-green rounded pill with white text
and icon. Group headings "MENU" and "GENERAL" in small grey uppercase letters.
Menu rows combine a thin line icon and label with generous vertical spacing.
A workspace card sits at the bottom.

**Reuse:**
- Narrow fixed sidebar with logo at top.
- Grouped navigation with small uppercase section labels.
- Filled dark-green active state; subtle hover on inactive rows.
- Icon + label alignment and comfortable row spacing.

**Adapt:**
- Replace brand with the supplied MY Trolley logo.
- Groups: "WORKSPACE" (Dashboard, Products, Categories, Stores, Product
  Attributes) and "ACCOUNT" (Profile/Logout) — only functions backed by real
  endpoints.
- Make it collapsible on desktop and a slide-over drawer on mobile.

**Avoid:**
- Copying "Members", "Usage & access", "Membership", "Invoices", "Support" and
  the workspace card — no such backend capability exists.
- Overloading the sidebar with decorative items.

---

## Reference 4 — `reference-4-product-cards.png`

**Observed:** Two-column grid of white product cards on a light background.
Each card: large centred product photo on white, bold product name, muted
"Local Farmers" sub-label, price with "per kg", and either a light "Add to Cart"
button or a dark-green quantity stepper. Consistent card proportions and
generous padding.

**Reuse:**
- Product-image-first presentation with generous white space.
- Clear name hierarchy: bold name, muted secondary line, emphasised price.
- Dark-green stepper styling as the basis for quantity controls elsewhere.

**Adapt:**
- Use for image galleries in product detail/edit screens and image-management
  thumbnails.
- Never display a single "global price" — the card layout is for imagery only;
  prices always come from a specific store association.
- Keep cards on image-management and detail screens, not as the main desktop
  product listing.

**Avoid:**
- Copying "Add to Cart", "per kg", farmer labels, or any shopping-cart flow —
  this is an administration platform, not a storefront.

---

## Reference 5 — `reference-5-product-rows.png`

**Observed:** Vertical list of cart rows on a light background. Each row: small
product thumbnail on the left, product name, muted quantity/weight line,
quantity stepper, current price with a struck-through original price, and an
"×" remove control on the right. Tight, consistent row rhythm with clear
separation and easy scanning.

**Reuse:**
- The compact row rhythm: thumbnail, primary text, secondary text, controls,
  trailing action.
- Clean dividers, consistent row height, restrained hover state.
- Quantity stepper as an inline editing control.

**Adapt:**
- Transform into a premium **desktop table** for product management with
  columns: Product image, Product name, Category, Attributes summary,
  Associated stores, Status, Actions.
- Store-specific price and quantity go into a details drawer / expandable row:
  e.g. "Store A — AED 15 — Qty 300", "Store B — AED 20 — Qty 200".
- On small screens, each table row becomes a card using the same row structure.

**Avoid:**
- Leaving the desktop listing as a shopping-cart list or product grid.
- Showing a struck-through "global price" — prices are store-specific only.
- Copying the "×" remove-cart semantics; destructive delete uses a confirmation
  dialog.

---

## Combined direction

- **Dashboard:** Reference 1 (compact colourful metric cards) + Reference 2
  (premium dark/light composition) — in MY Trolley colours and with real data.
- **Sidebar:** Reference 3 structure and active-state treatment.
- **Product imagery:** Reference 4 for galleries, thumbnails and image management.
- **Desktop product listing:** Reference 5's row design transformed into a
  structured, premium table with a store-specific details drawer.

One typography system, one spacing scale, one component library across all
screens. No unrelated business metrics or storefront interactions.
