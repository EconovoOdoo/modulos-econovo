# Tree View Enhancement - Field Implementation Proposals

## Summary
10 fields exist ✅ | 7 fields need creation ⚠️

## Progress Checklist

- [x] 1. Fc n° (invoice_numbers) - Multiple invoices ✅ IMPLEMENTED (Alt 1: many2many_tags)
- [x] 2. BL n° (bl_numbers) - Multiple shipments ✅ IMPLEMENTED (Alt 1: name_get() override)
- [x] 3. Cant cont (container_total_count) - Sum of containers ✅ IMPLEMENTED & FIXED
- [ ] 4. Producto (product_names) - Multiple products
- [ ] 5. Forma de pago (payment_term_id) - Payment Terms
- [ ] 6. N° despacho (customs_clearance_numbers) - Multiple clearances
- [ ] 7. Banco nominado (nominated_bank_id) - Nominated Bank
- [ ] 8. Update tree view XML with all 17 fields
- [x] 9. Change default view from kanban to tree ✅ DONE

---

## 1. Fc n° (invoice_numbers) - Multiple invoices

### Alternativa A ⭐ RECOMMENDED
**Type:** `Char` computed, stored, searchable
**Display:** "INV/2024/001, INV/2024/002 (3)"
```python
invoice_numbers = fields.Char(compute='_compute_invoice_numbers', store=True, string="Invoice Numbers")

@api.depends('invoice_ids.name')
def _compute_invoice_numbers(self):
    for record in self:
        if record.invoice_ids:
            names = record.invoice_ids.mapped('name')
            record.invoice_numbers = ', '.join(names[:3]) + (f' ({len(names)})' if len(names) > 3 else '')
        else:
            record.invoice_numbers = False
```

### Alternativa B
**Type:** `Many2many` with widget="many2many_tags"
- Display: Tags in tree
- More visual but takes more space

### Alternativa C
**Type:** `Integer` count only
- Display: "3 invoices"
- Less informative

---

## 2. BL n° (bl_numbers) - Multiple shipments ✅ IMPLEMENTED

**Implementation:** Using `shipment_ids` One2many with `many2many_tags` widget. BL number is now the `name` field.
**Display:** Individual BL numbers as clickable tags (max 5 visible)
**Pattern:** Following `stock.lot` pattern (name = real identifier + internal_reference for audit)

```python
# In models/comex_shipment.py
name = fields.Char(
    string="BL/AWB Number",
    required=True,
    copy=False,
    tracking=True,
    index='trigram',
    help="Bill of Lading or Air Waybill number - Primary identifier for this shipment.",
)
internal_reference = fields.Char(
    string="Internal Reference",
    readonly=True,
    copy=False,
    default=lambda self: _('New'),
    help="Internal tracking number (auto-generated for audit purposes).",
)

@api.model_create_multi
def create(self, vals_list):
    for vals in vals_list:
        if vals.get('internal_reference', _('New')) == _('New'):
            vals['internal_reference'] = self.env['ir.sequence'].next_by_code('comex.shipment')
    return super().create(vals_list)
```

```xml
<!-- In views/comex_operation_views.xml -->
<field name="shipment_ids" 
       widget="many2many_tags"
       string="BL Numbers"
       options="{'no_create': True, 'limit': 5}"
       optional="show"/>
```

**Benefits:**
- ✅ BL is the primary identifier (follows `stock.lot` pattern from Odoo native)
- ✅ Each BL is clickable (opens shipment detail)
- ✅ Limit of 5 tags prevents visual saturation
- ✅ BL appears everywhere: tags, breadcrumbs, selects, searches
- ✅ `internal_reference` maintains audit trail (SHP/2026/00001)
- ✅ No `name_get()` override needed (simpler, better performance)
- ✅ Indexed with trigram for fast searches
- ✅ Aligned with COMEX business logic (BL is the real identifier)

### ~~Alternativa A~~ (Not used)
**Type:** `Char` computed, stored, searchable
**Display:** "BL-123, BL-456 (2)"
```python
bl_numbers = fields.Char(compute='_compute_bl_numbers', store=True, string="BL Numbers")

@api.depends('shipment_ids.bl_number')
def _compute_bl_numbers(self):
    for record in self:
        if record.shipment_ids:
            bl_nums = record.shipment_ids.filtered('bl_number').mapped('bl_number')
            record.bl_numbers = ', '.join(bl_nums[:3]) + (f' ({len(bl_nums)})' if len(bl_nums) > 3 else '')
        else:
            record.bl_numbers = False
```

### Alternativa B
**Type:** `Text` with full list
- More complete but harder to read in tree

### Alternativa C
**Type:** `Char` with first only
- Display: "BL-123 (+2 more)"

---

## 3. Cant cont (container_total_count) - Sum of containers
**User Request:** Campo clickeable en tree view que abra listado de contenedores (como smart button)

### Alternativa A ⭐ RECOMMENDED - Integer + Action Method + Tree Button
**Type:** `Integer` computed, stored + action method
**Display:** Number "5" with clickable icon in tree view
**Behavior:** Click opens filtered list of all packages from operation's shipments

```python
# Field declaration
container_total_count = fields.Integer(
    compute='_compute_container_total_count', 
    store=True, 
    string="Total Containers"
)

# Compute method
@api.depends('shipment_ids.container_count')
def _compute_container_total_count(self):
    for record in self:
        record.container_total_count = sum(record.shipment_ids.mapped('container_count'))

# Action method (like smart buttons)
def action_view_containers(self):
    self.ensure_one()
    # Get all packages from all shipments
    packages = self.shipment_ids.mapped('package_ids')
    
    action = {
        'name': _('Containers'),
        'type': 'ir.actions.act_window',
        'res_model': 'stock.quant.package',
        'view_mode': 'tree,form',
        'domain': [('id', 'in', packages.ids)],
        'context': {
            'default_comex_operation_id': self.id,  # If field exists in package
        }
    }
    
    if len(packages) == 1:
        action['view_mode'] = 'form'
        action['res_id'] = packages.id
    
    return action
```

**Tree View XML:**
```xml
<tree>
    <field name="name"/>
    <!-- Other fields -->
    <field name="container_total_count"/>
    <button name="action_view_containers" 
            type="object" 
            icon="fa-cube" 
            title="View Containers"
            invisible="container_total_count == 0"
            class="oe_stat_button"/>
    <!-- More fields -->
</tree>
```

**Pros:**
- ✅ Muestra número simple y limpio
- ✅ Clickeable (botón con ícono)
- ✅ Abre listado filtrado de packages
- ✅ Patrón estándar (mismo que smart buttons)
- ✅ Sorteable por número
- ✅ Searchable

**Cons:**
- ⚠️ Ocupa 2 columnas (número + botón)
- ⚠️ Botón puede verse pequeño en tree

---

### Alternativa B - Many2many Computed with Packages (Directly Clickeable)
**Type:** `Many2many` computed, stored
**Display:** Shows package names as tags, clickeable
**Behavior:** Each tag opens the package, count badge is visible

```python
# Field declaration
package_ids = fields.Many2many(
    'stock.quant.package',
    compute='_compute_package_ids',
    store=True,
    string="Containers"
)

container_total_count = fields.Integer(
    compute='_compute_container_total_count',
    store=True,
    string="Total Containers"
)

# Compute methods
@api.depends('shipment_ids.package_ids')
def _compute_package_ids(self):
    for record in self:
        record.package_ids = record.shipment_ids.mapped('package_ids')

@api.depends('package_ids')
def _compute_container_total_count(self):
    for record in self:
        record.container_total_count = len(record.package_ids)
```

**Tree View XML:**
```xml
<tree>
    <field name="name"/>
    <!-- Option 1: Show count only -->
    <field name="container_total_count" string="Containers"/>
    <field name="package_ids" widget="many2many_tags" 
           string="Container Details" optional="hide"/>
    
    <!-- Option 2: Show tags (takes more space) -->
    <field name="package_ids" widget="many2many_tags"/>
</tree>
```

**Pros:**
- ✅ Tags son clickeables nativamente
- ✅ Puede mostrar nombres o solo count
- ✅ No requiere botón extra
- ✅ Filterable por package

**Cons:**
- ⚠️ Widget many2many_tags ocupa mucho espacio si se muestran
- ⚠️ Si solo muestras el count, NO es clickeable
- ⚠️ Less clean visually

---

### Alternativa C - Integer with Custom Widget (Clickeable Number)
**Type:** `Integer` computed, stored + custom JS widget
**Display:** Number "5" clickeable directly
**Behavior:** Click on number opens filtered list

```python
# Same field as Alternativa A
container_total_count = fields.Integer(
    compute='_compute_container_total_count', 
    store=True, 
    string="Total Containers"
)

@api.depends('shipment_ids.container_count')
def _compute_container_total_count(self):
    for record in self:
        record.container_total_count = sum(record.shipment_ids.mapped('container_count'))

def action_view_containers(self):
    # Same as Alternativa A
    ...
```

**Tree View XML:**
```xml
<tree>
    <field name="container_total_count" 
           widget="statinfo_clickable"
           options="{'action': 'action_view_containers'}"/>
</tree>
```

**JavaScript Required:** (static/src/js/container_count_widget.js)
```javascript
/** @odoo-module **/
import { registry } from "@web/core/registry";
import { IntegerField } from "@web/views/fields/integer/integer_field";

class ContainerCountClickable extends IntegerField {
    async onClick(ev) {
        ev.stopPropagation();
        await this.props.record.model.orm.call(
            this.props.record.resModel,
            'action_view_containers',
            [[this.props.record.resId]]
        ).then(action => {
            this.env.services.action.doAction(action);
        });
    }
}

ContainerCountClickable.template = "econovo_l10n_ar_comex.ContainerCountClickable";

registry.category("fields").add("statinfo_clickable", ContainerCountClickable);
```

**Pros:**
- ✅ Número directamente clickeable (más limpio)
- ✅ No requiere botón extra (1 sola columna)
- ✅ UX más intuitiva

**Cons:**
- ⚠️ Requiere JavaScript personalizado (~50 líneas)
- ⚠️ Requiere template XML para el widget
- ⚠️ Más complejo de mantener
- ⚠️ No es patrón estándar de Odoo

---

### Alternativa D - Char Field with HTML Link
**Type:** `Char` computed with HTML formatting
**Display:** "5 containers" as underlined link
**Behavior:** NOT truly clickeable in tree (requires form view)

```python
container_total_display = fields.Char(
    compute='_compute_container_total_display',
    string="Containers"
)

@api.depends('shipment_ids.container_count')
def _compute_container_total_display(self):
    for record in self:
        count = sum(record.shipment_ids.mapped('container_count'))
        record.container_total_display = f"{count} container{'s' if count != 1 else ''}"
```

**Pros:**
- ✅ Simple implementation
- ✅ Readable text

**Cons:**
- ❌ NOT clickeable in tree view
- ❌ HTML widget doesn't work in tree
- ❌ No cumple el objetivo

---

## Comparison Summary for Container Count

| Alternativa | Clickeable | Columns | Complexity | Standard Odoo | Clean UI |
|-------------|------------|---------|------------|---------------|----------|
| **A - Integer + Button** | ✅ Yes | 2 | ⭐ Low | ✅ Yes | ⭐⭐⭐ |
| **B - Many2many Tags** | ✅ Yes | 1-2 | ⭐ Low | ✅ Yes | ⭐⭐ |
| **C - Custom Widget** | ✅ Yes | 1 | ⭐⭐⭐ High | ❌ No | ⭐⭐⭐⭐ |
| **D - Char Display** | ❌ No | 1 | ⭐ Low | ✅ Yes | ⭐⭐ |

---

## Recommended Choice: **Alternativa A**

**Justification:**
- Patrón estándar de Odoo (igual que smart buttons)
- Fácil de implementar y mantener
- Clara separación: número (ordenable/buscable) + acción (clickeable)
- No requiere JavaScript custom
- Behavior predecible para usuarios de Odoo
- Si el botón molesta visualmente, puede estar en columna optional="hide"

**Implementation Preview:**
```
OI       | Partner  | Containers | [🔲] | ETD        | ...
---------|----------|------------|------|------------|----
COMEX001 | Supplier |     5      | 🔲   | 2026-01-15 | ...
COMEX002 | Client   |     2      | 🔲   | 2026-01-20 | ...
```

Click en 🔲 → Opens: "Containers (5)" tree/form view with filtered packages

---

## 4. Producto (product_names) - Multiple products from POs

### Alternativa A ⭐ RECOMMENDED
**Type:** `Char` computed, stored, searchable
**Display:** "Product A, Product B (3)"
```python
product_names = fields.Char(compute='_compute_product_names', store=True, string="Products")

@api.depends('purchase_order_ids.order_line.product_id.name')
def _compute_product_names(self):
    for record in self:
        if record.purchase_order_ids:
            products = record.purchase_order_ids.mapped('order_line.product_id')
            unique_products = products.mapped('display_name')
            record.product_names = ', '.join(unique_products[:3]) + (f' ({len(unique_products)})' if len(unique_products) > 3 else '')
        else:
            record.product_names = False
```

### Alternativa B
**Type:** `Many2many` computed (non-stored)
- Better for filtering but slower

### Alternativa C
**Type:** `Text` with full list
- Complete but takes more space

---

## 5. Forma de pago (payment_term_id) - Payment Terms ✅ IMPLEMENTED

**Implementation Status**: 🟢 COMPLETE & TESTED

**Type:** `Many2one('account.payment.term')`
**Standard Odoo:** Uses existing payment terms (Contabilidad > Configuración > Plazos de pago)

```python
# In models/comex_operation.py
payment_term_id = fields.Many2one(
    'account.payment.term',
    string="Payment Terms",
    tracking=True,
    help="Default payment terms for this COMEX operation",
)
```

**Tree View XML:**
```xml
<!-- In views/comex_operation_views.xml -->
<field name="payment_term_id" optional="show"/>
```

**Form View XML:**
```xml
<!-- In Financial page, amounts group -->
<group name="amounts">
    <field name="currency_id"/>
    <field name="payment_term_id"/>
    <field name="amount_fob"/>
    <!-- ... -->
</group>
```

**Benefits:**
- ✅ Uses native Odoo payment terms (immediate, net 30, net 60, etc.)
- ✅ Automatically available in tree and form views
- ✅ Searchable and filterable
- ✅ Can propagate to purchase orders if needed
- ✅ Standard field type (no custom logic needed)
- ✅ Tracking enabled for audit trail

**Placement:**
- **Tree View**: After BL Numbers, before invoices (financial flow visibility)
- **Form View**: Financial page > Amounts group (after currency, before FOB amounts)

### ~~Alternativa A~~ (Not used)
**Type:** `Many2one('account.payment.term')`
**Standard Odoo:** Uses existing payment terms
```python
payment_term_id = fields.Many2one(
    'account.payment.term',
    string="Payment Terms",
    help="Payment terms agreed for this COMEX operation"
)
```

### Alternativa B
**Type:** `Selection` with fixed options
- Options: ['prepaid', 'sight', 'credit_30', 'credit_60', 'lc']
- Less flexible

### Alternativa C
**Type:** `Char` free text
- Maximum flexibility but no standardization

---

## 6. N° despacho (customs_clearance_numbers) - Multiple clearances

### Alternativa A ⭐ RECOMMENDED
**Type:** `Char` computed, stored, searchable
**Display:** "DSP-001, DSP-002 (2)"
```python
customs_clearance_numbers = fields.Char(
    compute='_compute_customs_clearance_numbers', 
    store=True, 
    string="Customs Clearance Numbers"
)

@api.depends('customs_clearance_ids.name')
def _compute_customs_clearance_numbers(self):
    for record in self:
        if record.customs_clearance_ids:
            names = record.customs_clearance_ids.mapped('name')
            record.customs_clearance_numbers = ', '.join(names[:3]) + (f' ({len(names)})' if len(names) > 3 else '')
        else:
            record.customs_clearance_numbers = False
```

### Alternativa B
**Type:** `Many2many` with tags widget
- Visual but space-consuming

### Alternativa C
**Type:** `Integer` count only
- Just shows "2" (less informative)

---

## 7. Banco nominado (nominated_bank_id) - Nominated Bank

### Alternativa A ⭐ RECOMMENDED
**Type:** `Many2one('res.partner', domain=[('is_company', '=', True)])`
**Uses Partners:** Standard approach
```python
nominated_bank_id = fields.Many2one(
    'res.partner',
    string="Nominated Bank",
    domain=[('is_company', '=', True)],
    help="Bank nominated for this COMEX operation (LC, etc.)"
)
```

### Alternativa B
**Type:** `Many2one('res.bank')`
- Uses res.bank model
- Less flexible (no contacts, no accounting)

### Alternativa C
**Type:** Reference from MULC
- Related field from comex_mulc_ids.bank_partner_id
- Only works if MULC exists

---

## Implementation Priority Order

1. **Simple Fields** (No multi-value):
   - payment_term_id (Many2one)
   - nominated_bank_id (Many2one)
   - container_total_count (Integer compute)

2. **Multi-value Concatenated** (Searchable):
   - invoice_numbers (Char compute)
   - bl_numbers (Char compute)
   - product_names (Char compute)
   - customs_clearance_numbers (Char compute)

3. **View Updates**:
   - Update comex_operation_views.xml tree view
   - Change action view_mode from "kanban,tree,..." to "tree,kanban,..."

---

## Estimated Code Size
- 7 fields declarations: ~50 lines
- 7 compute methods: ~80 lines
- Tree view XML update: ~20 lines
- Total: ~150 lines

---

**Status:** ⏳ Awaiting user decision on which alternatives to implement
**Next:** User will indicate one by one which field/alternative to implement
