# Database Architecture — Milestone 2

This document describes the PostgreSQL database schema for the catalog domain, including entities, relationships, constraints, and indexes.

## Entity Relationship Diagram

```mermaid
erDiagram
    CATEGORY ||--o{ CATEGORY : "parent"
    CATEGORY ||--o{ PRODUCT : "has"
    PRODUCT ||--o{ PRODUCT_ATTRIBUTE : "has"
    PRODUCT ||--o{ PRODUCT_IMAGE : "has"
    PRODUCT }|--o{ PRODUCT_STORE : "associated"
    STORE }|--o{ PRODUCT_STORE : "stocks"

    CATEGORY {
        bigint id PK
        varchar(100) name UK
        varchar(110) slug UK
        text description
        bigint parent_id FK
        boolean is_active
        timestamp created_at
        timestamp updated_at
        %% unique lower(name)
    }

    STORE {
        bigint id PK
        varchar(100) name
        varchar(20) code UK
        text description
        text address
        boolean is_active
        timestamp created_at
        timestamp updated_at
        %% unique lower(code)
    }

    PRODUCT {
        bigint id PK
        varchar(200) name
        varchar(210) slug UK
        text description
        bigint category_id FK
        boolean is_active
        timestamp deleted_at "NULL until soft-deleted"
        timestamp created_at
        timestamp updated_at
    }

    PRODUCT_ATTRIBUTE {
        bigint id PK
        bigint product_id FK
        varchar(100) name
        text value
        timestamp created_at
        timestamp updated_at
        %% unique (product_id, name) and (product_id, lower(name))
    }

    PRODUCT_IMAGE {
        bigint id PK
        bigint product_id FK
        image image
        varchar(200) alt_text
        int display_order CHECK (display_order >= 0)
        boolean is_primary
        timestamp created_at
        timestamp updated_at
    }

    PRODUCT_STORE {
        bigint id PK
        bigint product_id FK
        bigint store_id FK
        decimal(12,4) price CHECK (price >= 0)
        int quantity CHECK (quantity >= 0)
        boolean is_available
        timestamp created_at
        timestamp updated_at
        %% unique (product_id, store_id)
    }
```

## Tables

### catalog_category

| Column | Type | Constraints |
|---|---|---|
| id | bigint | PRIMARY KEY |
| name | varchar(100) | UNIQUE, NOT NULL |
| slug | varchar(110) | UNIQUE, NOT NULL |
| description | text | |
| parent_id | bigint | FK → catalog_category(id), DEFERRABLE |
| is_active | boolean | DEFAULT true |
| created_at | timestamptz | NOT NULL |
| updated_at | timestamptz | NOT NULL |

**Constraints:**
- `catalog_category_name_key` — UNIQUE (name)
- `category_name_ci_unique` — UNIQUE (lower(name)) — case-insensitive protection at database level

**Indexes:**
- `category_active_idx` (is_active)
- `category_parent_idx` (parent_id, is_active)
- Unique indexes on name, slug and lower(name) (auto-created by constraints)

**Hierarchical categories:** Self-referential FK with `on_delete=PROTECT` prevents deletion of a category that has children.

---

### catalog_store

| Column | Type | Constraints |
|---|---|---|
| id | bigint | PRIMARY KEY |
| name | varchar(100) | NOT NULL |
| code | varchar(20) | UNIQUE, NOT NULL (stored uppercase) |
| description | text | |
| address | text | |
| is_active | boolean | DEFAULT true |
| created_at | timestamptz | NOT NULL |
| updated_at | timestamptz | NOT NULL |

**Constraints:**
- `catalog_store_code_key` — UNIQUE (code)
- `store_code_ci_unique` — UNIQUE (lower(code)) — also protects raw SQL writes that bypass `Store.save()` uppercasing

**Indexes:**
- `store_active_idx` (is_active)
- Unique indexes on code and lower(code) (auto-created by constraints)

---

### catalog_product

| Column | Type | Constraints |
|---|---|---|
| id | bigint | PRIMARY KEY |
| name | varchar(200) | NOT NULL |
| slug | varchar(210) | UNIQUE, NOT NULL |
| description | text | |
| category_id | bigint | FK → catalog_category(id), DEFERRABLE, PROTECT |
| is_active | boolean | DEFAULT true |
| deleted_at | timestamptz | NULL (set by soft deletion) |
| created_at | timestamptz | NOT NULL |
| updated_at | timestamptz | NOT NULL |

**Indexes:**
- `product_active_idx` (is_active)
- `product_category_idx` (category_id, is_active)
- Index on deleted_at (added in migration 0005)
- Unique index on slug (the redundant `product_slug_idx` was removed in migration 0004)

**Soft deletion:** `deleted_at IS NULL` means the product is live. Deleting sets
this timestamp; no row or related data is removed. `Product.objects` excludes
rows with a non-null `deleted_at`, so all ordinary queries, counts and related
managers hide them automatically. `Product.all_objects` is the unfiltered
manager used only for uniqueness checks and referential-integrity guards.

**Category protection:** `on_delete=PROTECT` prevents deleting a category that has products. The guard uses `Product.all_objects`, so soft-deleted products still protect their category.

---

### catalog_productattribute

| Column | Type | Constraints |
|---|---|---|
| id | bigint | PRIMARY KEY |
| product_id | bigint | FK → catalog_product(id), CASCADE |
| name | varchar(100) | NOT NULL |
| value | text | NOT NULL |
| created_at | timestamptz | NOT NULL |
| updated_at | timestamptz | NOT NULL |

**Constraints:**
- `unique_product_attribute_name` — UNIQUE (product_id, name)
- `product_attribute_name_ci_unique` — UNIQUE (product_id, lower(name)) — case-insensitive protection at database level

**Indexes:**
- Unique indexes on (product_id, name) and (product_id, lower(name)); the redundant `product_attr_name_idx` was removed in migration 0004

---

### catalog_productimage

| Column | Type | Constraints |
|---|---|---|
| id | bigint | PRIMARY KEY |
| product_id | bigint | FK → catalog_product(id), CASCADE |
| image | image | NOT NULL |
| alt_text | varchar(200) | |
| display_order | integer | NOT NULL, DEFAULT 0, CHECK (display_order >= 0) |
| is_primary | boolean | DEFAULT false |
| created_at | timestamptz | NOT NULL |
| updated_at | timestamptz | NOT NULL |

**Constraints:**
- `catalog_productimage_display_order_check` — CHECK (display_order >= 0) — created by `PositiveIntegerField`

**Indexes:**
- `product_img_primary_idx` (product_id, is_primary)

**Primary image enforcement:** Application-level logic in `save()` ensures only one primary image per product by setting `is_primary=False` on other images of the same product.

---

### catalog_productstore

**This is the core pricing/inventory junction table.**

| Column | Type | Constraints |
|---|---|---|
| id | bigint | PRIMARY KEY |
| product_id | bigint | FK → catalog_product(id), CASCADE, DEFERRABLE |
| store_id | bigint | FK → catalog_store(id), CASCADE, DEFERRABLE |
| price | numeric(12,4) | NOT NULL, CHECK (price >= 0) |
| quantity | integer | NOT NULL, DEFAULT 0, CHECK (quantity >= 0) |
| is_available | boolean | DEFAULT true |
| created_at | timestamptz | NOT NULL |
| updated_at | timestamptz | NOT NULL |

**Constraints:**
- `unique_product_store` — UNIQUE (product_id, store_id)
- `productstore_price_gte_zero` — CHECK (price >= 0)
- `catalog_productstore_quantity_check` — CHECK (quantity >= 0) — created by `PositiveIntegerField`

**Indexes:**
- `prod_store_avail_idx` (product_id, is_available)
- `store_prod_avail_idx` (store_id, is_available)
- `prod_store_price_idx` (price)
- Unique index on (product_id, store_id)

**Key design decisions:**
- **No global price/quantity on Product** — Price and quantity live only on the ProductStore association.
- **Independent store pricing** — Changing Store A's price never affects Store B.
- **Database-level CHECK constraints** — PostgreSQL rejects negative prices/quantities even for direct SQL inserts.
- **Decimal for money** — `numeric(12,4)` provides exact arithmetic; never use float.
- **Availability is explicit** — `is_available` is separate from quantity (zero quantity ≠ unavailable).

**Example:**
| Product | Store | Price | Quantity | Available |
|---|---|---:|---:|:---:|
| Milk | Store A | 15.0000 | 300 | true |
| Milk | Store B | 20.0000 | 200 | true |

---

## Foreign Key Deletion Behaviour

| Child Table | Parent Table | On Delete | Notes |
|---|---|---|---|
| catalog_category (self) | catalog_category | PROTECT | Prevents deleting parent with children |
| catalog_product | catalog_category | PROTECT | Prevents deleting category with products |
| catalog_productattribute | catalog_product | CASCADE | Attributes deleted only on a hard delete (soft deletion retains them) |
| catalog_productimage | catalog_product | CASCADE | Images deleted only on a hard delete (soft deletion retains them) |
| catalog_productstore | catalog_product | CASCADE | Associations deleted only on a hard delete (soft deletion retains them) |
| catalog_productstore | catalog_store | CASCADE | Associations deleted with store |

---

## Migrations

| Migration | Description |
|---|---|
| 0001_initial | Creates all six tables with PKs, FKs, unique constraints, indexes |
| 0002_alter_productstore_price | Changes price from decimal_places=2 to decimal_places=4 |
| 0003_add_price_check_constraint | Adds CHECK constraint `price >= 0` (database-level) |
| 0004_case_insensitive_uniqueness_and_index_cleanup | Adds case-insensitive UNIQUE constraints for category names, store codes and per-product attribute names; removes redundant `product_slug_idx`, `store_code_idx` and `product_attr_name_idx` |
| 0005_product_soft_delete | Adds nullable `deleted_at` to `catalog_product` with an index. Existing rows keep NULL (no data rewritten); no records are deleted or merged |

All migrations are applied and verified on PostgreSQL.

### Product lifecycle

| State | `is_active` | `deleted_at` | Admin listing | Inactive filter | Public catalogue | Editable / reactivatable |
|---|---|---|---|---|---|---|
| Active | true | NULL | Yes | No | Yes | Yes |
| Inactive | false | NULL | Yes | Yes | No | Yes |
| Deleted | unchanged | timestamp | No | No | No | No (normal endpoints return 404) |

Deactivation is a status change (`PATCH {"is_active": false}`). Deletion is a
separate operation (`DELETE /api/v1/products/{id}/`) that writes `deleted_at`
inside a transaction and keeps `is_active` unchanged. A soft-deleted product
is excluded from search, filters, sorting, pagination and counts. Its
attributes, images, store associations, prices and inventory are retained;
cloud image files are not removed. Because the row and its FK relationships
remain, soft-deleted products still protect their category and store from
deletion, and their unique slug remains reserved (new products with the same
name receive a numeric slug suffix).

### Django `on_delete` vs PostgreSQL `ON DELETE`

`on_delete=PROTECT` / `CASCADE` are Django ORM rules: they determine what the
ORM does when a Python model instance is deleted. PostgreSQL enforces the FK
with `ON DELETE NO ACTION` (DEFERRABLE INITIALLY DEFERRED), so direct SQL that
deletes a parent with children is rejected by the database rather than cascaded.
The API additionally checks associations before deleting a store and returns
`409 CONFLICT` when products are attached; this application-level protection is
preserved. The category guard uses the unfiltered product manager so historical
soft-deleted products keep protecting their category (migration 0005).

---

## Verification Queries

Run these on the database to verify constraints:

```sql
-- All CHECK constraints on productstore
SELECT conname, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE contype = 'c' AND conrelid = 'catalog_productstore'::regclass;

-- All constraints on productstore
SELECT conname, contype, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'catalog_productstore'::regclass;

-- Indexes
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'catalog_productstore';

-- Verify negative price is rejected
INSERT INTO catalog_productstore (product_id, store_id, price, quantity, is_available, created_at, updated_at)
VALUES (1, 1, -5.00, 10, true, NOW(), NOW());
-- ERROR:  new row for relation "catalog_productstore" violates check constraint "productstore_price_gte_zero"
```

---

## API Integration

All catalog endpoints are mounted under `/api/v1/` and require:
- `Authorization: Bearer <access_token>` (JWT from Milestone 1)
- `accounts.manage_catalog` permission (Administrator or DataEntry group)

Endpoints:
- `GET/POST /api/v1/categories/`
- `GET/PATCH/DELETE /api/v1/categories/{id}/`
- `GET/POST /api/v1/stores/`
- `GET/PATCH/DELETE /api/v1/stores/{id}/`
- `GET/POST /api/v1/products/`
- `GET/PATCH/DELETE /api/v1/products/{id}/`
- `GET/POST /api/v1/products/{product_id}/attributes/`
- `GET/PATCH/DELETE /api/v1/products/{product_id}/attributes/{attr_id}/`
- `GET/POST /api/v1/products/{product_id}/images/`
- `GET/PATCH/DELETE /api/v1/products/{product_id}/images/{image_id}/`
- `GET/POST /api/v1/products/{product_id}/stores/`
- `GET/PATCH/DELETE /api/v1/products/{product_id}/stores/{assoc_id}/`

Product list supports search, filtering (category, store, active, availability, price range), sorting (name, created_at, price with store), and pagination (max 100/page).