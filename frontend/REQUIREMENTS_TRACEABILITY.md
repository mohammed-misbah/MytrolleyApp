# MY Trolley — Frontend Requirements Traceability

Status values: **Verified** = implementation exercised during the completed
manual Tests 1–25 and FV.1–FV.7, or covered by the automated suite; **Pending**
= intentionally deferred work outside the current scope.

The original technical assessment is not present as a standalone file in the
repository. Its authoritative web-dashboard requirements are the ones stated in
the supplied milestone prompts; backend requirement IDs and verification
evidence are recorded in `docs/requirements-traceability.md`. This matrix maps
every stated frontend requirement to its implemented component, real backend
endpoint, interaction, validation and current status. Tests 26–29 (cloud image
storage, deployment/packaging, native iOS integration and final UI/UX polish)
are excluded from this verification.

---

## A. Authentication and authorised access

| ID | Requirement | Page / Component | Backend endpoint | Interaction | Validation | Test case | Status |
|---|---|---|---|---|---|---|---|
| AUTH-1 | Login interface | `pages/LoginPage` | `POST /api/v1/auth/login/` | Enter username/password, submit | Zod required fields; backend `400/401/429/413/415` envelope | Invalid credentials show generic error; 429 shows `Retry-After` | Verified |
| AUTH-2 | Token/session handling per backend | `services/auth`, `hooks/useAuth` | login response `access`; `POST /auth/refresh/`; `POST /auth/logout/` | Store access token in memory only; no localStorage | Never persist token; refresh via cookie requires `X-CSRFToken` from `csrftoken` cookie | Reload clears token; logout revokes all sessions | Verified |
| AUTH-3 | Protected dashboard routes | `routes/ProtectedRoute` | `GET /api/v1/auth/me/` | Redirect to login when no/invalid token | `401 TOKEN_INVALID / SESSION_REVOKED` → clear state | Direct URL visit without token → login | Verified |
| AUTH-4 | Unauthorised handling | `services/apiClient` interceptor | all endpoints | 401 → clear session + login; 403 → permission message | Error envelope `error.code`, `request_id` | Expired token → login; 403 message shown | Verified |
| AUTH-5 | Logout | `layout/Sidebar`, `hooks/useAuth` | `POST /api/v1/auth/logout/` | Click Logout → confirm → call → clear memory | Only clear local state after 200 exact message | Logout then protected route → login | Verified |
| AUTH-6 | Permission-aware UI | `hooks/usePermissions` | `/auth/me/` `user.permissions` | Show catalog navigation/actions only with `accounts.manage_catalog` | Backend remains authority; no client-side privilege escalation | DataEntry sees catalog actions; ungrouped user sees none | Verified |

## B. Dashboard

| ID | Requirement | Page / Component | Backend endpoint | Interaction | Validation | Test case | Status |
|---|---|---|---|---|---|---|---|
| DASH-1 | Professional responsive dashboard | `pages/DashboardPage`, `components/dashboard/*` | real catalog list endpoints | Landing view after login | No invented metrics | Visual review desktop + mobile | Verified |
| DASH-2 | Total / active products | `MetricCard` | `GET /products/?is_active=true`, `?is_active=false` (read `count`) | View metrics | Values derived from API `count` | Metric matches API count | Verified |
| DASH-3 | Categories count | `MetricCard` | `GET /categories/` | View metric | Array length from real response | Count equals API length | Verified |
| DASH-4 | Stores count | `MetricCard` | `GET /stores/` | View metric | Array length from real response | Count equals API length | Verified |
| DASH-5 | Product availability / store inventory | `dashboard/StoreInventoryPanel` | `GET /products/?store=<id>&is_available=true` | Select store, view counts | Store id from real stores list | Panel matches filtered API count | Verified |
| DASH-6 | Recent products | `dashboard/RecentProducts` | `GET /products/?ordering=-created_at&page_size=5` | View list | Real product rows only | Shows newest products from API | Verified |
| DASH-7 | Charts/statistics only with real data | `dashboard/Charts` (optional) | aggregate from list endpoints | View chart | Computed from API data; omitted when no data | No hardcoded numbers in source | Verified |

## C. Product management

| ID | Requirement | Page / Component | Backend endpoint | Interaction | Validation | Test case | Status |
|---|---|---|---|---|---|---|---|
| PROD-1 | Product listing | `pages/ProductsPage`, `components/products/ProductTable` | `GET /products/` | View paginated table | Real API data only | Table renders API rows | Verified |
| PROD-2 | Product creation | `pages/ProductFormPage` | `POST /products/` | Fill form, submit | RHF + Zod; backend errors mapped to fields | 201 → success toast; 400 → field errors | Verified |
| PROD-3 | Product viewing | `pages/ProductDetailPage` / DetailsDrawer | `GET /products/{id}/` | View nested attributes/images/associations | Read-only display | Nested data matches detail API | Verified |
| PROD-4 | Product editing | `pages/ProductFormPage` | `PATCH /products/{id}/` | Edit + submit | Partial payload only | 200 → list refresh | Verified |
| PROD-5 | Product deletion | `ProductsPage` action + `ConfirmDialog` | `DELETE /products/{id}/` | Confirm (with product name and catalogue-removal warning) → delete | Duplicate submissions blocked while request is in flight | 204 → "Product deleted successfully."; row removed, list and counts refreshed, last-page handled; 404/other errors surfaced | Verified |
| PROD-6 | Search / filter / sort / pagination | `components/products/ProductFilters` | `GET /products/?search=&category=&store=&is_active=&is_available=&min_price=&max_price=&ordering=&page=&page_size=` | Change filters | Server-side; no local filtering | Query params forwarded; max page size 100 | Verified |
| PROD-7 | Category selection | `ProductFormPage` category field | `GET /categories/` | Select from real categories | Required; invalid id rejected by backend | Form shows API categories | Verified |
| PROD-8 | Description/images/attributes/store associations in form | `ProductFormPage` sections | product + child endpoints | See D/E/G/I | See below | Full create flow end-to-end | Verified |

## D. Product creation and editing form

| ID | Requirement | Page / Component | Backend endpoint | Interaction | Validation | Test case | Status |
|---|---|---|---|---|---|---|---|
| FORM-1 | Organised sections | `ProductFormPage` | — | Sections: Basic info, Category, Attributes, Images, Store pricing | — | Visual review | Verified |
| FORM-2 | Name / description / category | RHF fields | `POST|PATCH /products/` | Input | Zod required name/category; backend final authority | Empty name blocked client-side; backend 400 surfaced | Verified |
| FORM-3 | Flexible attributes | `AttributesEditor` | `/products/{id}/attributes/` | Add/edit/remove rows | Non-empty name and value | Duplicate name → backend 400 shown | Verified |
| FORM-4 | One or more store associations, independent price/qty | `StoreAssociationEditor` | `/products/{id}/stores/` | Add store rows, set price & qty per row | Decimal price ≥ 0, integer qty ≥ 0; duplicate store blocked | Store A 15/300 and Store B 20/200 remain independent | Verified |
| FORM-5 | No global price/quantity | design token / types | — | — | `price`/`quantity` only inside store row types | Grep source for global price field → none | Verified |

## E. Product images

| ID | Requirement | Page / Component | Backend endpoint | Interaction | Validation | Test case | Status |
|---|---|---|---|---|---|---|---|
| IMG-1 | Multiple uploads / previews | `ImagesEditor` | `POST /products/{id}/images/` (multipart) | Select files → preview grid | Backend `DATA_UPLOAD_MAX_*` 262 144 bytes; max 10 files/request | Upload two images → both listed | Verified |
| IMG-2 | Primary selection / ordering / deletion | `ImagesEditor` | `PATCH /products/{id}/images/{image_id}/`, `DELETE ...` | Set primary, reorder, remove | One primary per product enforced by backend model | Primary switch → only one flagged | Verified |
| IMG-3 | Invalid type / oversize handling | `ImagesEditor` | upload endpoint | Show clear error | Client checks file type/size; backend 400 shown | TXT file rejected; oversize rejected | Verified |
| IMG-4 | Image URLs presented | `ProductImageRenderer` | `image_url` from serializer | Display thumbnail | Backend has no media-serving route; local file URLs are not served by Django | Browser image loading not verified | Pending (Test 26) |

## F. Categories

| ID | Requirement | Page / Component | Backend endpoint | Interaction | Validation | Test case | Status |
|---|---|---|---|---|---|---|---|
| CAT-1 | List / create / view / edit / delete | `pages/CategoriesPage` | `/categories/` CRUD | Table + form dialog | Name required; duplicate name → backend 400 | Full CRUD flow | Verified |
| CAT-2 | Category selection in product form | `ProductFormPage` | `GET /categories/` | Dropdown | Real IDs only | Options match API | Verified |
| CAT-3 | Search/pagination only if supported | `CategoriesPage` | `GET /categories/` (no pagination params) | — | Do not add frontend-only paging | Confirm no fake controls | Verified |

## G. Product attributes

| ID | Requirement | Page / Component | Backend endpoint | Interaction | Validation | Test case | Status |
|---|---|---|---|---|---|---|---|
| ATTR-1 | Flexible attributes | `AttributesEditor` | `/products/{pid}/attributes/` CRUD | Add name/value rows | Non-empty; backend uniqueness | Brand/Size/Colour/Weight rows work | Verified |
| ATTR-2 | No hardcoded attribute names | types/UI | — | Free-form key/value | — | Source review | Verified |

## H. Stores

| ID | Requirement | Page / Component | Backend endpoint | Interaction | Validation | Test case | Status |
|---|---|---|---|---|---|---|---|
| ST-1 | Store list/create/view/edit/delete | `pages/StoresPage` | `/stores/` CRUD | Table + form dialog | Name/code required; duplicate code → backend 400 | Full CRUD flow | Verified |
| ST-2 | Store selection in associations | `StoreAssociationEditor` | `GET /stores/` | Dropdown | Real IDs only | Options match API | Verified |

## I. Product-store associations (critical)

| ID | Requirement | Page / Component | Backend endpoint | Interaction | Validation | Test case | Status |
|---|---|---|---|---|---|---|---|
| PS-1 | Multiple stores per product | `StoreAssociationEditor`, `StoreInventoryPanel` | `/products/{pid}/stores/` CRUD | Add rows per store | Unique `(product, store)` | Two rows coexist | Verified |
| PS-2 | Independent price & quantity | store row component | POST/PATCH association | Edit one row | Decimal ≥ 0, int ≥ 0 | Update Store A → Store B unchanged | Verified |
| PS-3 | Duplicate prevention | store row component | POST → backend 409 | Attempt duplicate | Backend 409 mapped to friendly message | Duplicate rejected, no local success | Verified |
| PS-4 | Remove association | store row action + confirm | DELETE association | Confirm → delete | 204 only | Other store remains | Verified |
| PS-5 | Clear presentation of independence | DetailsDrawer | GET associations | Show "Store — AED x — Qty y" rows | No global summary price | Visual review | Verified |

## J. Search, filtering, sorting, pagination

| ID | Requirement | Page / Component | Backend endpoint | Interaction | Validation | Test case | Status |
|---|---|---|---|---|---|---|---|
| SRCH-1 | Server-side search | `ProductFilters` | `?search=` | Type in search | Debounced; API data only | Search returns backend results | Verified |
| SRCH-2 | Category/store/availability/price filters | `ProductFilters` | `?category=&store=&is_available=&min_price=&max_price=` | Select filters | Price filters require store | Filter params forwarded | Verified |
| SRCH-3 | Sorting | `ProductFilters` | `?ordering=name|created_at|price` (price needs store) | Select sort | Backend validates | Sort matches API | Verified |
| SRCH-4 | Pagination | `Pagination` | `?page=&page_size=` | Next/prev/page size | max 100 per backend | Page changes fetch new data | Verified |
| SRCH-5 | Loading / empty / error states | shared states | — | Skeletons, empty panel, retry | — | Visual review | Verified |

## K. Cross-cutting quality

| ID | Requirement | Implementation | Test case | Status |
|---|---|---|---|---|
| UX-1 | Success only after backend confirmation | mutation hooks | No toast on 4xx/5xx | Verified |
| UX-2 | Confirmation dialogs for destructive actions | `ConfirmDialog` | Cancel keeps record | Verified |
| UX-3 | Loading, empty, error, disabled, hover, focus states | UI primitives | States implemented; final visual polish is separate work | Implemented; visual review pending (Test 29) |
| RESP-1 | Desktop / laptop / tablet / mobile | responsive shell + table→cards | Responsive shell and table→card layout implemented; final multi-width review deferred | Pending (Test 29) |
| CODE-1 | All changes inside `frontend/` | directory inspection | Git status review | Verified |
| CODE-2 | Central Axios client, services, types, schemas, hooks | `src/services`, `src/types`, etc. | Source review | Verified |
| QA-1 | Real API data only; no mock presented as real | services | Network tab review | Verified |
| QA-2 | Visual verification in browser | Playwright/browser tool | Screenshots per page | Verified |
