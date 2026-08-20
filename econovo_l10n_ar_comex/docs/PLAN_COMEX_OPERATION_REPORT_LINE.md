# Implementation Plan — COMEX Operation Line Analysis

> **Audience**: AI coding agent (or developer) implementing this feature end-to-end.
> **Module**: `econovo_l10n_ar_comex` (Odoo 17, Econovo).
> **Status**: **Implemented** in version `17.0.5.0.0`. Validated on the local database
> (module install + 10/10 unit tests). Pending: staging validation with real data.
> **Author of the analysis**: GitHub Copilot, on request of Jose D. Leonett.
> **Date of the production audit**: 2026-08-19.

## 0. Deviations from the original design (applied during implementation)

1. **`_depends` is mandatory** on the report model. Without it the ORM does not flush the
   underlying tables before running the SQL view, so the report returns stale values
   (three unit tests failed exactly this way: a freshly written `date_etd` came back as
   `False`, a computed `vep_amount` as `0.0`, and an archived operation was still visible).
   The model now declares `_depends` for `comex.operation`, `comex.operation.product.line`,
   `comex.shipment` and `res.company`. **Any new column added to the SQL view must also be
   added to `_depends`.**
2. **`res.currency._get_query_currency_table` is NOT used.** It converts from *company*
   currency to the *user's* company currency, which does not match the per-row
   `company_currency_id` and reproduces the inconsistency core documents in
   `purchase.report` ("these reports are not multi-currency !!!"). The conversion now uses
   only `comex.operation.currency_rate`, so `*_company` columns are always expressed in the
   currency of the row's own company — consistent with `company_currency_id`. All Econovo
   companies are ARS, so the result is a single currency in practice; if a company with a
   different currency is ever added, group by **Company** before summing.
3. **The event-driven triggers already existed** for `purchase.order`, `purchase.order.line`
   and `sale.order`. Only `sale.order.line` was missing and was added.
4. **Translations (Phase 4) were not applied**: `i18n/es_AR.po` is a generated artefact and
   should be regenerated with the standard export, not hand-edited.

---

## 1. Goal

Today the user analyses COMEX data from the operation list
(`ir.actions.act_window` **id 1879**, model `comex.operation`, tree view id **6672** plus a
Studio extension id **6872**). That list has **one row per operation**.

The business need is the **same information but one row per product line**, keeping every
parent (import/export operation) column on each row, so the data can be filtered, grouped,
pivoted and exported at product granularity.

### Columns requested by the user (parent operation)

`color`, `name`, `partner_id`, `date_operation`, `tag_ids`, `date_etd`, `date_eta`,
`date_arrival`, `transport_mode`, `origin_country_id`, `container_total_count`,
`shipment_ids`, `payment_terms_display`, `nominated_bank_id`, `dispatch_invoice_numbers`,
`vep_amount`, `commercial_payment_status`, `customs_payment_status`,
`purchase_payment_status`, `sale_payment_status`, `company_id`.

> **Name correction (verified in production)**: the last two fields do **not** exist with
> those names. The real technical names are **`purchase_order_payment_status`** and
> **`sale_order_payment_status`**.

---

## 2. Verified facts (production `https://econovo.odoo.com`, read-only MCP audit)

| Fact | Value |
|---|---|
| Module version installed | `econovo_l10n_ar_comex` **17.0.4.12.0** (same as repo) |
| `comex.operation` records | **475** (434 `import`, 41 `export`), 2 archived |
| `comex.operation.product.line` records | **4 426**, **100 % `origin_type='purchase'`** |
| Operations with **zero** product lines | **153 / 475 (32 %)** — includes **all 41 exports** |
| Operation currencies | USD 440, CNY 18, EUR 17 → **multi-currency is real** |
| Company currencies | All 7 companies are **ARS** |
| `dispatch_invoice_numbers` | **`store=False`** (compute from `invoice_ids`, doc type `66`) |
| All other requested header fields | **stored** (`store=True`), including `payment_terms_display`, `container_total_count`, `vep_amount`, the 4 `*_payment_status` |
| `ir.rule` company on `comex.operation.product.line` | **DOES NOT EXIST** (exists for operation, shipment, stage, clearance, mulc) |
| ACL on `comex.operation.product.line` | read-only for `group_comex_user` and `group_comex_manager` |
| Existing action for lines | id **1883** `comex_operation_product_line_action`, `view_mode` in DB = `tree,form,pivot` (XML says `tree,form` → DB was changed outside the repo) |
| Studio artefacts | view **6872** (adds `color` + `product_line_ids` to the operation tree), view **7094** (default pivot for `comex.operation.product.line`) |
| `ir.filters` on these models | only one, on `comex.operation` (`PROVEEDORES`, group by `partner_id`) |
| UI language | `es_AR` |

### Existing technical debt found (must be handled — see Phase 1)

1. **Sync-on-read anti-pattern**: `comex.operation.product.line` overrides `search()` **and**
   `web_search_read()` to call `_sync_all_operations()`, which loops over ~434 operations and
   performs `sudo()` `create` / `write` / `unlink` **on every single read**. Opening any list of
   lines writes to the database. `_compute_product_line_count()` does the same.
2. The `search()` override declares `count=False`, a parameter that **no longer exists** in the
   Odoo 17 signature (`models.py:1606` → `def search(self, domain, offset=0, limit=None, order=None)`).
3. **Two competing sync implementations**: `comex.operation.product.line._sync_operation()` and
   `comex.operation._sync_product_lines_from_purchase()`.
4. **Multi-company leak**: no `ir.rule` on the line model.
5. **Export operations are never synced** — the sync only reads `purchase_order_ids` and only
   `state in ('purchase', 'done')`. `qty_delivered` is never written.
6. `comex.operation.product.line._compute_package_id()` runs one `stock.quant` search **per row**
   and `_search_package_id()` builds its domain from `product_id` only, ignoring the operation
   → cross-operation false positives. *(Out of scope for the report, documented for later.)*

---

## 3. Decisions taken (confirmed with the user)

| # | Decision |
|---|---|
| D1 | **Grain** = product line (`comex.operation.product.line`). |
| D2 | **Architecture** = read-only analysis model with a **SQL view** (`_auto = False` + `_table_query`), following the official `purchase.report` / `sale.report` pattern (also the OCA convention for `*.report` analysis models). |
| D3 | **Coverage** = also include **sale order lines (exports)** and a **synthetic row for operations with no lines** (so the 153 operations are not lost). |
| D4 | **Header amounts** = expose **both** the repeated header value (not summable) **and** a prorated per-line value (summable). |
| D5 | **Technical debt** = in scope: add the multi-company `ir.rule` **and** remove the sync-on-read (replace with event-driven sync on PO/SO + a nightly `ir.cron`). |
| D6 | **Delivery** = inside `econovo_l10n_ar_comex`, **replacing the current "Líneas de producto" action (id 1883)** so existing bookmarks `#action=1883` keep working. |

### Rejected alternatives (do not implement)

- **Stored `related` fields on `comex.operation.product.line`** — duplicates ~25 columns × 4 426
  rows, adds recompute triggers on every operation write, and still leaves the sync problem.
- **Non-stored `related` fields on the existing tree** — `fields.py:882`
  (`_description_sortable = (column_type and store) or ...`) means those columns would be
  **neither sortable nor groupable**, which defeats the analysis purpose.
- **SQL view reading `purchase_order_line` / `sale_order_line` directly** (bypassing
  `comex.operation.product.line`) — rejected because it would drop `origin_type='manual'` lines
  and create a second, divergent definition of "COMEX line".

---

## 4. Target design

### 4.1 New model

| Item | Value |
|---|---|
| Model name | **`comex.operation.report.line`** (Econovo guideline §3: report model = `<base_model>.report.<action>`) |
| Table | `comex_operation_report_line` |
| Python file | `econovo_l10n_ar_comex/report/comex_operation_report_line.py` |
| Views file | `econovo_l10n_ar_comex/report/comex_operation_report_line_views.xml` |
| `_auto` | `False` (SQL view via the `_table_query` property, **not** `init()` + `CREATE VIEW`) |
| `_description` | `'COMEX Operation Line Analysis'` |
| `_order` | `'date_operation desc, operation_name desc, sequence, id'` |
| `_rec_name` | `'operation_name'` |
| All fields | `readonly=True` |

`_table_query` (a `@property`, as in `purchase/report/purchase_report.py:54`) is required instead
of a static `CREATE VIEW` because the query must embed the **dynamic currency table**
(`res.currency._get_query_currency_table(self.env.companies.ids, date)`), which depends on the
allowed companies of the current user (`cids=` in the URL).

### 4.2 Row grain

```
one row per comex_operation_product_line
+ one synthetic row per comex_operation that has no product line at all
```

Primary key strategy (must stay deterministic across queries — do **not** use `ROW_NUMBER()`):

- real line row  → `id = pl.id * 2`      (even)
- synthetic row  → `id = op.id * 2 + 1`  (odd)

`has_product_line` (Boolean) distinguishes them and powers a search filter.

### 4.3 Column map

Legend: **H** = header value repeated on every line, **L** = line value,
**S** = prorated share (summable), **C** = converted to company currency (summable).

| Report field | Kind | Type | SQL source | Notes |
|---|---|---|---|---|
| `id` | — | Integer | see 4.2 | |
| `operation_id` | H | Many2one `comex.operation` | `pl.operation_id` / `op.id` | click-through |
| `product_line_id` | L | Many2one `comex.operation.product.line` | `pl.id` / `NULL` | |
| `has_product_line` | L | Boolean | `TRUE` / `FALSE` | |
| `sequence` | L | Integer | `pl.sequence` / `0` | |
| `active` | H | Boolean | `op.active` | enables `active_test` (archived hidden by default) |
| `operation_name` | H | Char | `op.name` | user asked for `name`; renamed to avoid clashing with the line description |
| `operation_type` | H | Selection `import/export` | `op.operation_type` | drives `invisible=` on the status columns |
| `stage_id` | H | Many2one `comex.operation.stage` | `op.stage_id` | |
| `color` | H | Integer | `op.color` | `widget="color_picker"` (parity with Studio view 6872) |
| `partner_id` | H | Many2one `res.partner` | `op.partner_id` | |
| `date_operation` | H | Date | `op.date_operation` | |
| `date_etd` / `date_eta` / `date_arrival` | H | Date | idem | |
| `transport_mode` | H | Selection | `op.transport_mode` | |
| `origin_country_id` | H | Many2one `res.country` | `op.origin_country_id` | |
| `container_total_count` | H | Integer | `op.container_total_count` | stored compute, safe |
| `payment_terms_display` | H | Char | `op.payment_terms_display` | stored compute, safe |
| `nominated_bank_id` | H | Many2one `res.partner` | `op.nominated_bank_id` | |
| `commercial_payment_status` | H | Selection | `op.commercial_payment_status` | same 4 values + same `decoration-*` as the parent tree |
| `customs_payment_status` | H | Selection | `op.customs_payment_status` | idem |
| `purchase_order_payment_status` | H | Selection | `op.purchase_order_payment_status` | `invisible="operation_type != 'import'"` |
| `sale_order_payment_status` | H | Selection | `op.sale_order_payment_status` | `invisible="operation_type != 'export'"` |
| `company_id` | H | Many2one `res.company` | `op.company_id` | `groups="base.group_multi_company"` |
| `currency_id` | H | Many2one `res.currency` | `op.currency_id` | `column_invisible="1"` |
| `currency_ars_id` | H | Many2one `res.currency` | `op.currency_ars_id` | `column_invisible="1"` |
| `company_currency_id` | H | Many2one `res.currency` | `comp.currency_id` | `column_invisible="1"` |
| `bl_numbers` | H | Char | `string_agg(sh.name, ', ')` | groupable/exportable version of `shipment_ids` |
| `tag_ids` | H | Many2many `comex.operation.tag` | **`related='operation_id.tag_ids'`** | non-stored → filterable, **not** sortable/groupable |
| `shipment_ids` | H | One2many `comex.shipment` | **`related='operation_id.shipment_ids'`** | idem; display parity with the parent tree |
| `dispatch_invoice_numbers` | H | Char | **`related='operation_id.dispatch_invoice_numbers'`** | source is `store=False` → **not** sortable/groupable, computed per row |
| `product_id` | L | Many2one `product.product` | `pl.product_id` | |
| `product_tmpl_id` | L | Many2one `product.template` | `pl.product_tmpl_id` | |
| `product_uom_id` | L | Many2one `uom.uom` | `pl.product_uom` | renamed to follow the `_id` suffix guideline |
| `product_qty` | L | Float | `pl.product_qty` | `sum=` OK |
| `qty_received` / `qty_delivered` | L | Float | idem | `sum=` OK |
| `price_unit` | L | Float | `pl.price_unit` | **no** `sum=` |
| `price_subtotal` | L | Monetary(`currency_id`) | `pl.price_subtotal` | **no** `sum=` (mixed currencies) |
| `price_subtotal_company` | L·C | Monetary(`company_currency_id`) | see 4.5 | **`sum=`** |
| `origin_type` | L | Selection | `pl.origin_type` | |
| `purchase_order_id` / `sale_order_id` | L | Many2one | `pl.purchase_order_id` / `pl.sale_order_id` | |
| `line_share` | L | Float | see 4.4 | `optional="hide"`, `digits=(16, 6)` |
| `vep_amount` | H | Monetary(`currency_ars_id`) | `op.vep_amount` | **no** `sum=` |
| `vep_amount_share` | S | Monetary(`currency_ars_id`) | `op.vep_amount * line_share` | **`sum=`** |
| `amount_fob` / `amount_cif` | H | Monetary(`currency_id`) | `op.amount_fob` / `op.amount_cif` | **no** `sum=` |
| `amount_fob_share_company` / `amount_cif_share_company` | S·C | Monetary(`company_currency_id`) | see 4.5 | **`sum=`** |

> **Hard rule for the tree view**: a column may only carry `sum=` if it is expressed in a
> **single** currency across all rows (i.e. company currency, or ARS for VEP). Every column in
> the operation currency must be rendered **without** `sum=`, otherwise USD + CNY + EUR get added
> together.

### 4.4 Proration factor

```sql
line_share = CASE
    WHEN ot.lines_total > 0 THEN pl.price_subtotal / ot.lines_total
    ELSE 1.0 / ot.line_count          -- equal split when total is 0 or negative
END
```

with, per operation:

```sql
ot.line_count  = COUNT(*)
ot.lines_total = SUM(pl.price_subtotal)
```

Synthetic rows use `line_share = 1.0` (the whole header value belongs to that single row).

Guarantee: `SUM(line_share) = 1.0` per operation → `SUM(vep_amount_share)` over a full operation
equals its `vep_amount`. **This invariant must be covered by a unit test.**

### 4.5 Company-currency conversion

All Econovo companies use **ARS**, while operations are in USD / CNY / EUR. Therefore
`currency_table.rate` alone is not enough — a per-operation rate is required, exactly like
`purchase.order.currency_rate` (`purchase/models/purchase_order.py:145,181`).

**Add to `comex.operation`** (new stored field):

```python
currency_rate = fields.Float(
    string="Currency Rate",
    compute='_compute_currency_rate',
    compute_sudo=True,
    store=True,
    readonly=True,
    digits=(12, 6),
    help="Ratio between the operation currency and the company currency.",
)

@api.depends('currency_id', 'company_id', 'date_operation')
def _compute_currency_rate(self):
    for operation in self:
        operation.currency_rate = self.env['res.currency']._get_conversion_rate(
            operation.company_id.currency_id,
            operation.currency_id,
            operation.company_id,
            operation.date_operation,
        )
```

Then in SQL:

```sql
-- amounts expressed in the operation currency
(<amount> / COALESCE(NULLIF(op.currency_rate, 0), 1.0)) * COALESCE(ct.rate, 1.0)
-- vep_amount is already in ARS (== company currency)
(op.vep_amount * <line_share>) * COALESCE(ct.rate, 1.0)
```

`ct` is the currency table joined on `ct.company_id = op.company_id`, produced by
`self.env['res.currency']._get_query_currency_table(self.env.companies.ids, fields.Date.today())`
(`account/models/res_currency.py:45`). The `account` dependency is already declared in the manifest.

### 4.6 Reference SQL skeleton

```python
@property
def _table_query(self):
    return '%s %s %s' % (self._with(), self._select_lines(), self._select_operations_without_lines())
```

```sql
WITH operation_totals AS (
    SELECT
        pl.operation_id      AS operation_id,
        COUNT(*)             AS line_count,
        SUM(pl.price_subtotal) AS lines_total
    FROM comex_operation_product_line pl
    GROUP BY pl.operation_id
)
SELECT
    pl.id * 2                                   AS id,
    pl.id                                       AS product_line_id,
    TRUE                                        AS has_product_line,
    pl.sequence                                 AS sequence,
    pl.operation_id                             AS operation_id,
    op.active                                   AS active,
    op.name                                     AS operation_name,
    op.operation_type                           AS operation_type,
    ...
    CASE WHEN ot.lines_total > 0
         THEN pl.price_subtotal / ot.lines_total
         ELSE 1.0 / ot.line_count
    END                                         AS line_share,
    (
        SELECT string_agg(sh.name, ', ' ORDER BY sh.name)
        FROM comex_shipment sh
        WHERE sh.operation_id = op.id AND sh.active
    )                                           AS bl_numbers
FROM comex_operation_product_line pl
JOIN comex_operation op            ON op.id = pl.operation_id
JOIN operation_totals ot           ON ot.operation_id = pl.operation_id
JOIN res_company comp              ON comp.id = op.company_id
LEFT JOIN {currency_table} ct      ON ct.company_id = op.company_id

UNION ALL

SELECT
    op.id * 2 + 1                               AS id,
    NULL                                        AS product_line_id,
    FALSE                                       AS has_product_line,
    0                                           AS sequence,
    op.id                                       AS operation_id,
    ...
    1.0                                         AS line_share,
    ( ... same string_agg ... )                 AS bl_numbers
FROM comex_operation op
JOIN res_company comp              ON comp.id = op.company_id
LEFT JOIN {currency_table} ct      ON ct.company_id = op.company_id
WHERE NOT EXISTS (
    SELECT 1 FROM comex_operation_product_line pl WHERE pl.operation_id = op.id
)
```

**Both branches of the `UNION ALL` must project the exact same columns, in the exact same order,
with the same PostgreSQL types.** Cast explicitly where a `NULL` is projected
(`NULL::integer AS product_line_id`, `NULL::numeric AS product_qty`, …).

---

## 5. Implementation phases

### Phase 0 — Preparation

1. Work on a feature branch off the Econovo working branch (see repo memory
   `git_submodule_structure.md`; **never** push directly to `Econovo` / `econovo`).
2. Bump `__manifest__.py` version `17.0.4.12.0` → **`17.0.5.0.0`** (new feature + behaviour change).
3. Validate against **local** (`http://localhost:8071`) first, then **staging**
   (`https://econovo-pruebas.odoo.com`). **Production is read-only.**

### Phase 1 — Technical debt on `comex.operation.product.line` (blocking)

**File**: `models/comex_operation_product_line.py`

1. **Delete** the `search()` override and the `web_search_read()` override entirely.
2. **Delete** the sync call inside `comex.operation._compute_product_line_count()`.
3. Consolidate the sync into **one** public entry point on the line model:
   `_sync_operations(operations)` → per operation, reconcile PO lines **and** SO lines.
   Remove `comex.operation._sync_product_lines_from_purchase()` (dead duplicate) and make
   `comex.operation.action_sync_product_lines()` delegate to the surviving implementation.
4. Extend the sync to sale orders:
   - source: `operation.sale_order_ids` filtered on `state in ('sale', 'done')` and
     `so.comex_operation_id == operation`;
   - map `sale.order.line` → `origin_type='sale'`, `sale_line_id`, `qty_delivered`;
   - skip display/section/note lines (`sol.display_type`) and, for POs, keep the existing behaviour.
5. **Event-driven triggers** (replaces sync-on-read). Keep them small and extendable:
   - `purchase.order.line`: `create` / `write` / `unlink` → resync `line.order_id.comex_operation_id`.
   - `purchase.order`: `write` touching `state` or `comex_operation_id` → resync old **and** new operation.
   - `sale.order.line` / `sale.order`: same shape.
   - Guard every trigger with `if self.env.context.get('comex_skip_line_sync'): return` and call
     the sync with `.with_context(comex_skip_line_sync=True)` to avoid recursion.
6. **Nightly safety net**: `data/comex_cron.xml` → `ir.cron` "COMEX: Resynchronise product lines",
   `model_comex_operation_product_line`, `code: model._cron_sync_all_operations()`, interval 1 day,
   `noupdate="1"` block. The cron method processes operations in batches and logs a summary.
7. **Uniqueness** (prevents duplicated rows in the report):
   ```python
   _sql_constraints = [
       ('purchase_line_uniq', 'unique(purchase_line_id)',
        'A purchase order line can only be linked to one COMEX product line.'),
       ('sale_line_uniq', 'unique(sale_line_id)',
        'A sale order line can only be linked to one COMEX product line.'),
   ]
   ```
   PostgreSQL allows multiple `NULL`s in a unique constraint, so manual lines are unaffected.
   → requires the pre-migration in Phase 6.
8. **Multi-company rule** — `security/econovo_l10n_ar_comex_security.xml` (inside the existing
   `<data noupdate="1">`):
   ```xml
   <record id="comex_operation_product_line_rule_company" model="ir.rule">
       <field name="name">COMEX Operation Product Line: Company</field>
       <field name="model_id" ref="model_comex_operation_product_line"/>
       <field name="domain_force">[
           '|',
           ('company_id', '=', False),
           ('company_id', 'in', company_ids)
       ]</field>
       <field name="groups" eval="[(4, ref('base.group_user'))]"/>
   </record>
   ```
   Add the equivalent rule for the new report model (Phase 3).

> Do **not** touch `_compute_package_id` / `_search_package_id` in this work item. Record it as a
> separate follow-up ticket (see §7, item 12).

### Phase 2 — `comex.operation.currency_rate`

Add the field described in §4.5 to `models/comex_operation.py`, respecting the class element order
(field declaration in the "Amounts" block, compute method with the other computes).
The stored value backfills automatically on module upgrade for the 475 existing records.

### Phase 3 — The report model and its views

1. Create the `report/` package: `report/__init__.py`, add `from . import report` to the module
   `__init__.py`, and `from . import comex_operation_report_line` to `report/__init__.py`.
2. Implement `report/comex_operation_report_line.py` following §4 and the structure of
   `odoo-17/odoo/addons/purchase/report/purchase_report.py` (`_select()`, `_from()`,
   `_where()` helpers so submodules can extend the query — Econovo guideline §4 "Think Extendable").
3. Implement `report/comex_operation_report_line_views.xml`:
   - `comex_operation_report_line_view_tree` — read-only tree
     (`create="false" edit="false" delete="false"`), column order identical to the parent tree
     (view 6672) with the line columns inserted after `operation_name`; keep the same
     `optional="show"/"hide"` flags and the same `decoration-*` on the 4 status badges;
     `decoration-muted="not has_product_line"` to visually mark the synthetic rows.
   - `comex_operation_report_line_view_search` — search fields (`operation_name`, `partner_id`,
     `product_id`, `purchase_order_id`, `sale_order_id`, `bl_numbers`), filters
     (`Imports`, `Exports`, `Without product lines` → `[('has_product_line','=',False)]`,
     `From purchase` / `From sale`, ETA this month, archived) and a **Group By** group
     (operation, partner, product, stage, transport mode, origin country, company, **currency**,
     `date_operation:month`).
   - `comex_operation_report_line_view_pivot` and `..._view_graph` — default measures
     `price_subtotal_company` and `product_qty`.
4. **Replace the entry point** — edit the existing record in
   `views/comex_operation_product_line_views.xml` **keeping the same XML id** so DB id 1883 and
   any `#action=1883` bookmark survive:
   ```xml
   <record id="comex_operation_product_line_action" model="ir.actions.act_window">
       <field name="name">COMEX Line Analysis</field>
       <field name="res_model">comex.operation.report.line</field>
       <field name="view_mode">tree,pivot,graph</field>
       <field name="search_view_id" ref="comex_operation_report_line_view_search"/>
       <field name="context">{}</field>
       <field name="help" type="html"> ... </field>
   </record>
   ```
   Rename `menu_comex_operation_product_lines` to **"Line Analysis"** (keep the XML id).
   Keep the raw-line views (`comex_operation_product_line_view_tree` / `_form`) — they are still
   used by the smart button `comex.operation.action_view_product_lines()`.
5. Register both new files in `__manifest__.py` `data` (after the existing view files) and add
   the two ACL lines to `security/ir.model.access.csv`:
   ```csv
   access_comex_operation_report_line_user,comex.operation.report.line.user,model_comex_operation_report_line,group_comex_user,1,0,0,0
   access_comex_operation_report_line_manager,comex.operation.report.line.manager,model_comex_operation_report_line,group_comex_manager,1,0,0,0
   ```
   plus the company `ir.rule` for the report model.

### Phase 4 — Translations

Add the new user-facing strings to `i18n/es_AR.po` (or regenerate the `.pot`). All source strings
in the code stay in **English** and go through `_()`. Suggested labels:
`COMEX Line Analysis` → `Análisis de líneas COMEX`, `Without product lines` → `Sin líneas de producto`,
`VEP Share` → `VEP prorrateado`, `Prorated` → `Prorrateado`.

### Phase 5 — Tests

`tests/test_comex_operation_report_line.py` (`@tagged('post_install', '-at_install')`,
`TransactionCase`). Minimum coverage:

1. An operation with N lines produces exactly N rows; each row carries the header values.
2. An operation with **no** lines produces exactly **1** row with `has_product_line = False`.
3. `SUM(line_share) == 1.0` per operation (float tolerance), including the 0-total fallback.
4. `SUM(vep_amount_share) == operation.vep_amount` per operation.
5. Export operation with a confirmed SO → rows with `origin_type = 'sale'` and `qty_delivered`.
6. Archived operation → excluded by default, visible with `active_test=False`.
7. **Multi-company**: a user restricted to company A cannot read rows of company B — assert on
   **both** `comex.operation.product.line` and `comex.operation.report.line`.
8. **No write on read**: `self.env['comex.operation.report.line'].search([])` and
   `comex.operation.product.line.search([])` must not change `write_date` of any line
   (regression test for the removed sync-on-read).
9. Currency conversion: an operation in USD yields `price_subtotal_company` in ARS consistent with
   `currency_rate`.

Run:
```powershell
Set-Location D:\Odoo\ODOO-SRC; .\odoo-manager.ps1 -Action test-ce -TestModule "econovo_l10n_ar_comex"
```
```powershell
Get-Content D:\Odoo\ODOO-SRC\odoo-17\odoo\odoo.log -Tail 200 | Select-String -Pattern "(ERROR|FAIL|test_|passed|failed)"
```

### Phase 6 — Migration

`migrations/17.0.5.0.0/pre-migrate.py` (follow the style of `migrations/17.0.4.11.0/pre-migrate.py`):

1. **Deduplicate** `comex_operation_product_line` on `purchase_line_id` and on `sale_line_id`
   (keep the lowest `id`) **before** the new `_sql_constraints` are applied, otherwise the upgrade
   aborts. Log how many rows were removed.
2. Log a warning listing operations that will now surface as synthetic rows (count only).

`migrations/17.0.5.0.0/post-migrate.py`:

3. Trigger one full `_cron_sync_all_operations()` run so the 41 export operations get their lines.

### Phase 7 — UI validation (local, Chrome DevTools MCP)

1. Navigate to `http://localhost:8071`, open **COMEX → Operations → Line Analysis**.
2. Verify: the list loads with no error; every requested column is present; the 4 status badges
   keep their colours; `optional` columns toggle correctly; sorting works on the SQL columns;
   grouping by operation / product / currency works; the pivot opens.
3. Verify the synthetic rows appear (filter *Without product lines*) and are visually muted.
4. Verify `#action=1883` still resolves.
5. Check the browser console and the server log for errors.

---

## 6. Edge cases — catalogue and required handling

| # | Edge case | Evidence | Required handling |
|---|---|---|---|
| 1 | 153 operations (32 %), incl. **all 41 exports**, have no product line and would vanish | production count | Synthetic `UNION ALL` row + `has_product_line` filter (§4.2) |
| 2 | Sync only covers **confirmed POs** (`purchase`, `done`); RFQ/draft/cancelled excluded | `_sync_operation()` | Documented limitation; keep the same states for SOs (`sale`, `done`). Do **not** silently widen it |
| 3 | Sync writes on every read → slow + writes in read transactions | `search()` / `web_search_read()` overrides | Phase 1: remove overrides, event-driven + cron |
| 4 | No `ir.rule` on the line model → cross-company leak | production `ir.rule` audit | Phase 1.8 + rule for the report model |
| 5 | Archived operations (2) would still show their lines | line model has no `active` | `active` column in the SQL view → `active_test` handles it |
| 6 | `dispatch_invoice_numbers` is `store=False` | `ir.model.fields` | Expose as non-stored `related` → display + filter only. **Never** add `sum=`/group-by. If sorting is required later, make it stored on `comex.operation` with `@api.depends('invoice_ids.l10n_latam_document_number', 'invoice_ids.l10n_latam_document_type_id')` |
| 7 | `tag_ids` / `shipment_ids` are x2many → cannot be SQL columns | ORM | Non-stored `related` for display parity + `bl_numbers` (`string_agg`) for grouping/export |
| 8 | Summing header amounts multiplies them by the line count (e.g. VEP × 13) | design | Header columns rendered **without** `sum=`; only `*_share*` columns are summable |
| 9 | Mixed currencies (USD 440 / CNY 18 / EUR 17) in one total | production count | Only company-currency columns carry `sum=`; add a **Currency** group-by; `currency_rate` on the operation (§4.5) |
| 10 | Operation with `lines_total = 0` or negative → share explodes | design | `CASE ... ELSE 1.0 / line_count` fallback + unit test |
| 11 | Duplicate lines for the same PO/SO line | no constraint today | `_sql_constraints` + dedup pre-migration |
| 12 | `package_id` / `container_number` cost one `stock.quant` search per row and `_search_package_id` ignores the operation | `comex_operation_product_line.py` | **Excluded from the report.** Separate follow-up ticket |
| 13 | `qty_received` / `price_unit` are snapshots copied by the sync; once sync-on-read is gone they can go stale | Phase 1 | Cron + event triggers; optionally switch to `related` on `purchase_line_id` in a follow-up |
| 14 | Studio layer (views 6872 / 7094) lives only in the DB | production audit | Do **not** rely on it. `color` must be declared in the module code. Warn the user that Studio view 7094 becomes orphan when action 1883 changes model |
| 15 | Action 1883 `view_mode` was changed in the DB (`tree,form,pivot`) outside the repo | production audit | That edit also set **`noupdate = true`** on its `ir.model.data` row (Odoo Studio flags every record it touches), so the 17.0.5.0.0 upgrade silently skipped the action. Fixed by `migrations/17.0.5.0.1/pre-migrate.py`, which clears the flag before the data files are loaded |
| 16 | Saved favourites (`ir.filters`) on `comex.operation.product.line` would break when action 1883 changes model | audit found **none** today | Re-check right before deploying to production |
| 24 | Renaming a record's source label leaves the previous translation in the DB, so the UI keeps the old name | staging showed "Líneas de producto" | Same pre-migration strips the non-`en_US` keys of the action/menu labels, and `i18n/es_AR.po` provides the new Spanish terms |
| 17 | Report row `id`s are synthetic | design | Deterministic arithmetic ids (`*2`, `*2+1`), never `ROW_NUMBER()` |
| 18 | `name` is ambiguous (operation reference vs. line description) | model | Report exposes `operation_name` (header) and `name` is **not** reused |
| 19 | `vep_amount` is ARS while `amount_fob/cif` follow the operation currency | model | Two distinct currency fields (`currency_ars_id`, `currency_id`), both `column_invisible="1"` |
| 20 | 4 426 rows today and growing; default action limit 80 | production count | Keep `limit` at 80, rely on the underlying indexes (`operation_id`, `product_id`, `purchase_line_id`, `sale_line_id` are all `index=True`) |
| 21 | Odoo 17 `search()` has no `count` parameter | `models.py:1606` | Removed with the override in Phase 1 |
| 22 | `_get_query_currency_table` lives in `account`, not `base` | `account/models/res_currency.py:45` | Not used in the end — see deviation 2 in §0 |
| 23 | A SQL-view model reads stale data unless the ORM is told what to flush | 3 failing unit tests | `_depends` declared on the report model (deviation 1 in §0) |

---

## 7. Mandatory coding conventions for the implementer

- Follow `.github/instructions/Al crear modulos personalizados de Odoo17 para econovo.instructions.md`.
- **Odoo 17**: never `attrs` / `states`; use `invisible="..."`, `readonly="..."`, `column_invisible="1"`.
- XML ids: `<model>_view_<type>`, `<model>_action`, `<model>_rule_<group>`.
- Python: class element order (private attrs → defaults → fields → computes → selections →
  constrains/onchange → CRUD → actions → business), import order, `_()` on every user-facing string.
- **Never** `cr.commit()`.
- Split the SQL into `_select()` / `_from()` / `_where()` / `_with()` helpers so it stays extendable.
- Code and comments in **English only**; UI strings translated in `i18n/es_AR.po`.
- PowerShell: use `;`, never `&&`.
- Verify model/field structure with MCP (`describe_model`, `search_read`) before writing code —
  do not guess field names.

---

## 8. Acceptance criteria

1. **COMEX → Operations → Line Analysis** opens a list with one row per product line and every
   column listed in §1 (using the corrected `*_order_payment_status` names).
2. Operations without product lines appear exactly once, visually muted, and are reachable through
   the *Without product lines* filter.
3. Export operations show rows sourced from their sale order lines.
4. `SUM` in the list is only offered on single-currency columns; the prorated columns sum back to
   the header value per operation.
5. A user limited to one company sees only that company's rows (report **and** raw line model).
6. Opening the list performs **zero** writes (verified in the log / by `write_date`).
7. The full test suite of `econovo_l10n_ar_comex` passes on local and on staging.
8. `#action=1883` still opens the new analysis list.

---

## 9. Open questions to confirm before/while implementing

1. **Manual lines** (`origin_type='manual'`): none exist today. Confirm they must appear in the
   report (current design: yes, they are ordinary rows).
2. **`qty_delivered` for exports**: confirm the expected source is `sale.order.line.qty_delivered`
   (delivered quantity) and not a customs/nationalisation milestone.
3. **`bl_numbers`**: should archived shipments be excluded (current design: yes, `sh.active`)?
4. **Proration basis**: `price_subtotal` share was chosen. Confirm this over quantity or weight for
   VEP/customs allocation (a customs-correct allocation is normally by CIF value, which matches
   `price_subtotal` only when the line prices are CIF).
5. **Follow-up ticket** for `package_id` / `_search_package_id` (edge case 12) — confirm it is
   accepted as out of scope here.
6. **Deployment window**: the upgrade rewrites action 1883 and runs a dedup migration; confirm the
   staging → production sequence and who validates.

---
---

# Part 2 — Stock location traceability per line

> **Scope extension** requested on 2026-08-20. Target version: **`17.0.6.0.0`**.
> **Status**: **implemented**, 22/22 unit tests green on the local database.

## 10. Goal

The end user must be able to answer, for the units of a given COMEX line: **where is this stock
right now?** — through the whole COMEX chain and, for machines, also after nationalisation
(own warehouse, dealer, customer, return).

## 11. Verified facts (staging audit, 2026-08-20)

### 11.1 The COMEX stock circuit

Built by `res.company._create_comex_stock_infrastructure()` (`models/res_company.py`):

```
Supplier → [COMEX/IN] → En Viaje → [COMEX/ARR] → En Puerto → [COMEX/FIS] → Depósito Fiscal → [COMEX/NAC] → WH/Stock
```

- 4 picking types per company (`is_comex_import = True`), chained by **push rules** with
  `auto = 'manual'` (each step is triggered by hand).
- Each company owns its **own** `COMEX Transit` location tree (ids 62310/62312 for one company,
  62316 and 62320 for the others) — **the location names repeat across companies**.
- Hundreds of pickings in use, with many `waiting` (27-30 per type) and `cancel` (10-12 per type).

### 11.2 Traceability reality

| Fact | Value | Consequence |
|---|---|---|
| Product catalogue by tracking | **36 145 `none` / 414 `serial` / 7 `lot`** | Lot-based tracking alone covers ~1 % of products |
| Quants in COMEX locations | 96, of which **only 6 carry a lot**, none carries a package | `stock.lot.location_id` cannot be the primary mechanism |
| Machines (compactadores, cargadores, palas) | **`tracking = 'serial'`** | The high-value COMEX goods *are* traceable per unit |
| Stock currently in COMEX locations | En Viaje 6 u · Depósito Fiscal 705 u | Untracked spare parts are the bulk of the volume |
| Dealer locations `AGROV/Conce/<DEALER>` | `usage = 'internal'` | Machines at dealers are still own stock → quants locate them exactly |
| Chained moves (ARR/FIS/NAC) | `purchase_line_id = False`, but carry `comex_operation_id` (`index=True`) and `move_orig_ids` | Attribution needs a dedicated link |
| Merged moves | Observed (`move_orig_ids: [291120, 379033]`) | A chained move can aggregate several origins |

### 11.3 Core extension points confirmed

| Point | Location | Use |
|---|---|---|
| `stock.rule._push_prepare_move_copy_values` | already overridden in `models/stock_rule.py` | Propagate the new field through the push chain |
| `stock.move._prepare_merge_moves_distinct_fields()` | `stock/models/stock_move.py:1002` | Prevent merging moves of different lines |
| `stock.lot.location_id` | `stock/models/stock_lot.py:55,138` | Non-stored compute, `False` when the lot sits in several locations |
| `stock.picking.return_id` / `return_ids` | `stock/models/stock_picking.py:410` | Identify returns |
| `stock.move.origin_returned_move_id` | `stock/models/stock_move.py:143` | Identify return moves at move level |

## 12. Decisions taken (confirmed with the user)

| # | Decision |
|---|---|
| D7 | **Mechanisms**: current location through the move chain (**A**) + lot/serial location (**C**). Quantity-per-stage columns (**B**) are **rejected**: they would hardcode the COMEX stages and break when new stages are added. Container-based (**D**) rejected: almost no packages in use. |
| D8 | **Multiple locations are shown as tags**, like `comex.operation.shipment_ids` in the operation form (`widget="many2many_tags"`), and the field must be **filterable**. |
| D9 | **Attribution**: dedicated **`stock.move.comex_product_line_id`**. Reusing `purchase_line_id` is rejected (see §13). |
| D10 | **Backfill**: only for **serial-tracked products**. |
| D11 | **Returned** is defined by the existence of a **return picking/move** for that serial, not by location. |
| D12 | **Location tags include every location**, internal and customer/supplier, plus a status column derived from the location `usage`. |
| D13 | **Untracked products** stop at nationalisation (last internal location reached). |
| D14 | **Exports**: left blank for now, separate scope. |
| D15 | **Exposure**: line analysis report, product lines tab of the operation, search filters/group by, and operation header summary. |

## 13. Rejected: propagating `purchase_line_id` to the chained moves

The user asked to evaluate this. **It must not be done.**

`purchase.order.line.move_ids` is `One2many('stock.move', 'purchase_line_id')`
(`purchase_stock/models/purchase_order_line.py:26`) and `_compute_qty_received` sums over that
One2many (`:50-75`). The COMEX chain has **4 steps**, so a line of 2 units would report
`qty_received = 8` once ARR/FIS/NAC are validated. That corrupts:

- purchase invoicing on received quantities and `qty_to_invoice`;
- the 3-way match;
- `line_pickings` (`:182`), which filters `move_ids.picking_id` by destination usage.

And `_push_prepare_move_copy_values` runs for **every** push rule in the database, not only COMEX,
so the damage would not be contained to this module.

**Replacement**: a dedicated field, propagated by the same already-COMEX-scoped override.

## 14. Target design

### 14.1 `stock.move.comex_product_line_id` (new)

```python
comex_product_line_id = fields.Many2one(
    'comex.operation.product.line',
    string="COMEX Product Line",
    copy=True,
    index='btree_not_null',
    ondelete='set null',
    help="COMEX product line these units belong to. Propagated through push rules.",
)
```

Assignment and propagation:

1. **Origin moves**: `comex.operation.product.line._assign_stock_moves()`, called at the end of
   `_sync_operation()`, writes the field on `purchase_line_id.move_ids` / `sale_line_id.move_ids`
   that do not have it yet, and then walks `move_dest_ids` forward to cover moves that already
   exist.
2. **New chained moves**: add the field to the existing
   `stock_rule._push_prepare_move_copy_values()` override, next to `comex_operation_id`. It is only
   written when the source move has it, so **non-COMEX flows are untouched**.
3. **Merging**: override `stock.move._prepare_merge_moves_distinct_fields()` to append
   `'comex_product_line_id'`, so moves belonging to different lines are never merged.
4. **Backorders / copies**: `copy=True` propagates automatically.

`ondelete='set null'` matters because the synchronisation **unlinks obsolete product lines**;
`_assign_stock_moves()` re-links on the next sync.

### 14.2 `comex.operation.product.line` — where the logic lives

The real model owns the computation; the SQL report only exposes `related` fields. This keeps the
report free of heavy SQL and makes the same information available in the operation form.

| Field | Type | Content |
|---|---|---|
| `move_ids` | One2many(`stock.move`, `comex_product_line_id`) | The whole chain of this line |
| `current_location_ids` | Many2many(`stock.location`), compute + **search** | Every location where the line's units currently are |
| `lot_ids` | Many2many(`stock.lot`), compute | Serial/lot numbers received for this line |
| `stock_status` | Selection, compute + **search** | `pending` / `internal` / `partial` / `delivered` / `returned` / `unknown` |
| `current_location_display` | Char, **stored** (materialised) | Sortable, groupable and exportable text version of the locations |
| `lot_name_display` | Char, **stored** (materialised) | Sortable text version of the serial numbers |
| `last_delivery_partner_id` | Many2one(`res.partner`), **stored** | Contact of the last validated transfer |

**`current_location_ids` algorithm** (batched, never one query per row):

1. If the product is tracked (`tracking in ('serial', 'lot')`) **and** the line has lots →
   locations of `stock.quant` of those lots with `quantity > 0`. This follows the units anywhere:
   COMEX transit, own warehouse, `AGROV/Conce/<DEALER>` (internal), customer locations, and back
   after a return.
2. Otherwise → net position from the **done** moves of `move_ids`: per location,
   `sum(quantity moved in) - sum(quantity moved out)`, keeping only locations with a positive
   balance. For untracked products this naturally stops at the warehouse location reached on
   nationalisation (D13).
3. No done move → empty, `stock_status = 'pending'`.

Nothing in this algorithm names a COMEX stage: it derives the locations from the data, so adding a
new stage to the circuit later requires **no code change** (D7).

**`stock_status`** is derived from `location.usage` only (generic, no hardcoded names), except
`returned`, which uses the core return linkage (D11): a `done` `stock.move.line` for one of the
line's lots whose `move_id.origin_returned_move_id` is set (equivalently, whose picking has
`return_id`).

| Value | Condition |
|---|---|
| `pending` | No done move yet |
| `internal` | All units in `internal` (or company `transit`) locations |
| `delivered` | All units in `customer` locations |
| `partial` | Units split between internal and customer/supplier locations |
| `returned` | A return move exists for its lots and the units are internal again |

**`_search_current_location_ids`** must translate a domain leaf into a search over
`stock.quant` (tracked) / `stock.move` (untracked) and return `[('id', 'in', line_ids)]`, so the
column is filterable (D8). Support at least `in`, `not in`, `=`, `!=`, `child_of`.

### 14.3 Exposure (D15)

| Place | Change |
|---|---|
| `comex.operation.report.line` | `current_location_ids`, `lot_ids`, `stock_status` as **non-stored `related`** through `product_line_id`. Tags widget, `optional="show"` for locations and status, `optional="hide"` for lots. No `_depends` entry needed (related fields are not SQL columns). |
| `comex_operation_product_line_view_tree` / `_view_form` | Same three fields |
| `comex_operation_report_line_view_search` | Search field on `current_location_ids`, filters by `stock_status`, group by `stock_status` |
| `comex.operation` form | `current_location_ids` computed as the union of its product lines' locations, shown as tags next to the existing `current_location_id` |

## 15. Edge cases and required handling

| # | Edge case | Handling |
|---|---|---|
| 25 | Chained moves lose `purchase_line_id` | Dedicated `comex_product_line_id` propagated by the push-rule override (§14.1) |
| 26 | Propagating `purchase_line_id` would inflate `qty_received` ×4 | Rejected, documented in §13 |
| 27 | Merged moves with several origins | `comex_product_line_id` added to `_prepare_merge_moves_distinct_fields()` |
| 28 | Product lines are deleted and recreated by the sync | `ondelete='set null'` + re-link in `_assign_stock_moves()` |
| 29 | Same product in two lines of the same operation | Solved exactly by the dedicated field (this was the main reason to add it) |
| 30 | **Untracked historical lines have no backfill (D10)** | They show **no location** until a new move is generated. See §18 open question 7 — a fallback by `(operation, product)` is recommended |
| 31 | Cancelled moves/pickings (10-12 per type) | Excluded: only `state = 'done'` counts for the net position |
| 32 | Units split across stages (2 at port, 1 in fiscal) | Several tags, one per location (D8) |
| 33 | A serial sitting in several locations | `stock.lot.location_id` returns `False` in that case — do **not** use it; compute from `stock.quant` directly |
| 34 | Location names repeat across companies | Display `complete_name` and always filter by the line `company_id` |
| 35 | Machine delivered to a dealer | `AGROV/Conce/...` is `internal` → tag shows the dealer, `stock_status = 'internal'` |
| 36 | Machine delivered to a real customer | Customer-usage location tag, `stock_status = 'delivered'` (D12) |
| 37 | Machine returned | `stock_status = 'returned'` via the core return linkage (D11) |
| 38 | Untracked goods after nationalisation | Last internal location reached; no further tracking (D13) — documented limitation |
| 39 | Export operations | Left empty (D14) |
| 40 | Manual lines (`origin_type = 'manual'`) | No PO/SO line → no moves → empty |
| 41 | Performance on 4 426 lines | Batched computes (one `read_group` per model for the whole recordset), `index='btree_not_null'` on the new field |
| 42 | Report rows without a product line (synthetic) | Related fields are empty — correct |
| 43 | Multi-company record rules | The computes must run on the line's company; use `sudo()` only where the existing COMEX fields already require it |
| 44 | **User edits `stock.lot.location_id` by hand** | That field is `store=True, readonly=False` with an inverse (`stock/models/stock_lot.py:55,143`). Writing it calls `quants.move_quants(...)` → `_get_inventory_move_values` with **`is_inventory=True`** (`stock_quant.py:1285`): real moves, with no picking and **without** `comex_product_line_id`. Handled by reading the **quants**, never `lot.location_id`, so the relocation is reflected immediately. Note the inverse **raises `UserError`** when the lot sits in more than one location, which is precisely why `lot.location_id` cannot be used as a source |
| 45 | Untracked goods moved outside the COMEX chain (inventory adjustment, manual transfer) | The chain balance alone would keep pointing at the old location. Mitigated by a reality check: a location is only reported if `stock.quant` still holds stock of that product there; otherwise the line falls to `stock_status = 'unknown'` |
| 46 | Lines whose historical moves were never linked | Automatic fallback matching moves by `(comex_operation_id, product_id)`, so the 705 untracked units already in Depósito Fiscal are located without a full backfill (resolves open question 7) |
| 47 | **Sorting by location** | A Many2many is never sortable and a non-stored compute cannot be ordered (`fields.py:882`). Solved by materialising `current_location_display`, `lot_name_display` and `last_delivery_partner_id`: stored columns on the line, selected as **real SQL columns** by the report view. Refreshed by `stock.move._action_done()` (including the inventory moves of a manual lot relocation), by `_assign_stock_moves()` and by the daily cron |
| 48 | Contact of the current location | `stock.lot.last_delivery_partner_id` only considers **outgoing** transfers (`_get_outgoing_domain`, `stock_lot.py:245`), so it stays empty when a machine is sent to a dealer through an internal transfer. The line field falls back to the partner of the last validated transfer, covering dealers and customers alike |

## 16. Implementation phases

1. **Model**: `stock.move.comex_product_line_id` + `_prepare_merge_moves_distinct_fields` override
   + `_push_prepare_move_copy_values` propagation.
2. **Assignment**: `comex.operation.product.line._assign_stock_moves()` wired into `_sync_operation()`.
3. **Computes**: `move_ids`, `current_location_ids` (+ `_search_...`), `lot_ids`, `stock_status`,
   `current_location_display`.
4. **Views**: product line tree/form, report tree, report search, operation form.
5. **Migration `17.0.6.0.0`**: backfill `comex_product_line_id` for **serial-tracked products only**
   (D10), walking `move_orig_ids` back to the move that still has `purchase_line_id`, then mapping
   it to the product line. Log how many moves were linked and how many could not be resolved.
6. **Tests** (see §17).
7. **Local validation** + staging validation with the real machines.

## 17. Tests to add

1. A line whose moves reached "Depósito Fiscal" reports exactly that location.
2. A line split across two stages reports **both** locations.
3. A serial-tracked line delivered to a dealer (`internal`) reports the dealer location and
   `stock_status = 'internal'`.
4. A serial-tracked line delivered to a customer reports `stock_status = 'delivered'`.
5. A returned serial reports `stock_status = 'returned'`.
6. An untracked line stops at the warehouse location after nationalisation.
7. A cancelled chain does not contribute any location.
8. **`qty_received` regression**: after validating the full COMEX chain, `purchase.order.line.qty_received`
   equals the received quantity **once** (guards §13).
9. Two lines of the same operation with the same product report their own locations independently.
10. `_search_current_location_ids` returns the expected lines for `in` / `child_of`.
11. Batched compute: reading 50 lines does not issue one query per line.

## 18. Open questions for Part 2

7. **Untracked historical lines (edge case 30)**: **resolved** — implemented as the automatic
   fallback by `(operation, product)` described in edge case 46, on top of the serial-only backfill.
8. **`stock_status` labels**: confirm the Spanish wording (`Pendiente`, `En stock propio`,
   `Entregado`, `Devuelto`, `Parcial`, `Sin determinar`).
9. **Operation header**: `current_location_id` (manual) and `current_location_ids` (computed) are
   currently shown side by side; confirm whether the manual one should be dropped.
10. **Pending chain vs. actual location**: if a user relocates a lot manually while COMEX steps are
    still pending, those pickings become inconsistent. Not surfaced today; a `has_pending_chain`
    indicator is the natural follow-up.
