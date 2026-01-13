# Product Lines View - Analysis & Implementation Proposals

## Business Context

**Problem:** Displaying products in tree view of operations would saturate the interface when operations have multiple products/POs/SOs.

**Solution Inspiration:** OCA Purchase Request module pattern:
- **View 1**: Purchase Requests (header perspective)
- **View 2**: Purchase Request Lines (line item perspective)

**Requirement:**
1. Table showing all products associated with operations (from POs or SOs)
2. Fields similar to `sale.order.line` / `purchase.order.line`
3. Two menu entries: "Operations" (current) + "Product Lines" (new)
4. Avoid saturating operation tree view with product tags

---

## Current Data Structure

```
comex.operation (1)
  ├─► purchase.order (N) [import]
  │    └─► purchase.order.line (N)
  │         └─► product.product (1)
  │
  └─► (future) sale.order (N) [export]
       └─► sale.order.line (N)
            └─► product.product (1)
```

**Challenge:** Multiple levels of indirection (operation → order → order.line → product)

---

## Proposal A: New Model `comex.operation.product.line` ⭐ RECOMMENDED

**Concept:** Create dedicated line model (like purchase.request.line pattern)

### Data Model

```python
class ComexOperationProductLine(models.Model):
    _name = 'comex.operation.product.line'
    _description = 'COMEX Operation Product Line'
    _order = 'operation_id, sequence, id'
    
    # Header relation
    operation_id = fields.Many2one('comex.operation', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    
    # Product info
    product_id = fields.Many2one('product.product', required=True)
    product_tmpl_id = fields.Many2one('product.template', related='product_id.product_tmpl_id')
    name = fields.Text(string='Description', required=True)
    
    # Quantities
    product_qty = fields.Float(string='Quantity', required=True)
    product_uom = fields.Many2one('uom.uom', string='UoM', required=True)
    qty_received = fields.Float(string='Received', readonly=True)  # Import
    qty_shipped = fields.Float(string='Shipped', readonly=True)    # Export
    
    # Pricing (currency from operation)
    currency_id = fields.Many2one(related='operation_id.currency_id')
    price_unit = fields.Float(string='Unit Price', required=True)
    price_subtotal = fields.Monetary(compute='_compute_price_subtotal', store=True)
    
    # Origin tracking
    origin_type = fields.Selection([
        ('purchase', 'Purchase Order'),
        ('sale', 'Sale Order'),
        ('manual', 'Manual Entry'),
    ], string='Origin', required=True, default='manual')
    purchase_line_id = fields.Many2one('purchase.order.line', string='PO Line')
    sale_line_id = fields.Many2one('sale.order.line', string='SO Line')
    
    # Related order (for navigation)
    purchase_order_id = fields.Many2one(related='purchase_line_id.order_id', store=True)
    sale_order_id = fields.Many2one(related='sale_line_id.order_id', store=True)
    
    # Computed fields
    @api.depends('product_qty', 'price_unit')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.product_qty * line.price_unit
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.display_name
            self.product_uom = self.product_id.uom_id
```

### Synchronization Logic

```python
# In comex.operation
@api.depends('purchase_order_ids.order_line', 'sale_order_ids.order_line')
def _compute_product_line_ids(self):
    """Auto-sync product lines from PO/SO lines."""
    for operation in self:
        # Collect all lines
        lines_to_create = []
        
        # From Purchase Orders (Import)
        for po_line in operation.purchase_order_ids.mapped('order_line'):
            lines_to_create.append({
                'operation_id': operation.id,
                'product_id': po_line.product_id.id,
                'name': po_line.name,
                'product_qty': po_line.product_qty,
                'product_uom': po_line.product_uom.id,
                'price_unit': po_line.price_unit,
                'qty_received': po_line.qty_received,
                'origin_type': 'purchase',
                'purchase_line_id': po_line.id,
            })
        
        # From Sale Orders (Export)
        for so_line in operation.sale_order_ids.mapped('order_line'):
            lines_to_create.append({
                'operation_id': operation.id,
                'product_id': so_line.product_id.id,
                'name': so_line.name,
                'product_qty': so_line.product_uom_qty,
                'product_uom': so_line.product_uom.id,
                'price_unit': so_line.price_unit,
                'qty_shipped': so_line.qty_delivered,
                'origin_type': 'sale',
                'sale_line_id': so_line.id,
            })
        
        # Replace all lines
        operation.product_line_ids = [(5, 0, 0)]  # Delete all
        operation.product_line_ids = [(0, 0, vals) for vals in lines_to_create]
```

### Views

**Tree View (Product Lines Perspective):**
```xml
<record id="view_comex_operation_product_line_tree" model="ir.ui.view">
    <field name="name">comex.operation.product.line.tree</field>
    <field name="model">comex.operation.product.line</field>
    <field name="arch" type="xml">
        <tree create="false" delete="false" edit="false">
            <field name="operation_id"/>
            <field name="product_id"/>
            <field name="name"/>
            <field name="product_qty"/>
            <field name="product_uom"/>
            <field name="price_unit"/>
            <field name="price_subtotal"/>
            <field name="origin_type"/>
            <field name="purchase_order_id" optional="show"/>
            <field name="sale_order_id" optional="show"/>
            <field name="qty_received" optional="show"/>
            <field name="qty_shipped" optional="show"/>
        </tree>
    </field>
</record>
```

**Menu Structure:**
```xml
<menuitem id="menu_comex_operations_root" name="COMEX Operations"/>

<!-- View 1: Operations (header) -->
<menuitem id="menu_comex_operations" 
          parent="menu_comex_operations_root"
          action="action_comex_operation"
          sequence="10"/>

<!-- View 2: Product Lines (lines) -->
<menuitem id="menu_comex_product_lines" 
          parent="menu_comex_operations_root"
          name="Product Lines"
          action="action_comex_operation_product_line"
          sequence="20"/>
```

### Pros ✅
- ✅ Clean separation (operations vs product lines)
- ✅ Standard Odoo pattern (header + lines)
- ✅ Easy to extend with computed fields
- ✅ Good performance (stored data)
- ✅ Can add manual lines (not just from POs/SOs)
- ✅ Independent filtering/grouping on product lines
- ✅ Clear ownership (cascade delete)

### Cons ⚠️
- ⚠️ Data duplication (lines stored twice: in PO/SO and here)
- ⚠️ Requires sync mechanism (compute or write hooks)
- ⚠️ ~200 lines of code (model + views + sync logic)
- ⚠️ More complex to maintain

### Use Cases
- ✅ "Show me all operations importing Product X"
- ✅ "Total quantity of Product Y across all operations"
- ✅ "Group by product to see which operations contain each product"
- ✅ "Search operations by product code/name"

---

## Proposal B: SQL View (Read-Only, No Duplication) ⭐⭐ LIGHTWEIGHT

**Concept:** Use PostgreSQL VIEW to query lines directly from PO/SO without storing duplicates

### Data Model

```python
class ComexOperationProductLine(models.Model):
    _name = 'comex.operation.product.line'
    _description = 'COMEX Operation Product Line (View)'
    _auto = False  # Don't create table (manual SQL)
    _order = 'operation_id, product_id'
    
    # Fields (read-only)
    id = fields.Integer(readonly=True)
    operation_id = fields.Many2one('comex.operation', readonly=True)
    product_id = fields.Many2one('product.product', readonly=True)
    name = fields.Text(readonly=True)
    product_qty = fields.Float(readonly=True)
    product_uom = fields.Many2one('uom.uom', readonly=True)
    price_unit = fields.Float(readonly=True)
    price_subtotal = fields.Monetary(readonly=True)
    origin_type = fields.Selection([
        ('purchase', 'Purchase Order'),
        ('sale', 'Sale Order'),
    ], readonly=True)
    purchase_order_id = fields.Many2one('purchase.order', readonly=True)
    sale_order_id = fields.Many2one('sale.order', readonly=True)
    currency_id = fields.Many2one('res.currency', readonly=True)
    
    def init(self):
        """Create SQL VIEW combining PO lines and SO lines."""
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                -- Purchase Order Lines (Import)
                SELECT
                    pol.id AS id,
                    po.comex_operation_id AS operation_id,
                    pol.product_id AS product_id,
                    pol.name AS name,
                    pol.product_qty AS product_qty,
                    pol.product_uom AS product_uom,
                    pol.price_unit AS price_unit,
                    (pol.product_qty * pol.price_unit) AS price_subtotal,
                    'purchase' AS origin_type,
                    po.id AS purchase_order_id,
                    NULL::integer AS sale_order_id,
                    po.currency_id AS currency_id
                FROM purchase_order_line pol
                JOIN purchase_order po ON pol.order_id = po.id
                WHERE po.comex_operation_id IS NOT NULL
                
                UNION ALL
                
                -- Sale Order Lines (Export)
                SELECT
                    sol.id + 1000000 AS id,  -- Offset to avoid ID collision
                    so.comex_operation_id AS operation_id,
                    sol.product_id AS product_id,
                    sol.name AS name,
                    sol.product_uom_qty AS product_qty,
                    sol.product_uom AS product_uom,
                    sol.price_unit AS price_unit,
                    sol.price_subtotal AS price_subtotal,
                    'sale' AS origin_type,
                    NULL::integer AS purchase_order_id,
                    so.id AS sale_order_id,
                    so.currency_id AS currency_id
                FROM sale_order_line sol
                JOIN sale_order so ON sol.order_id = so.id
                WHERE so.comex_operation_id IS NOT NULL
            )
        """)
```

### Pros ✅
- ✅ **Zero data duplication** (just a view)
- ✅ Always in sync (reads directly from source)
- ✅ Simple implementation (~100 lines)
- ✅ Good performance (PostgreSQL optimizes)
- ✅ No write hooks needed

### Cons ⚠️
- ⚠️ **Read-only** (cannot create/edit lines here)
- ⚠️ Requires `sale.order.comex_operation_id` field for exports
- ⚠️ ID collision handling needed (offset)
- ⚠️ Limited compute field support

### Use Cases
- ✅ "Show me all products in operations" (read-only)
- ✅ "Search operations by product"
- ✅ "Group by product"
- ❌ Cannot add manual lines
- ❌ Cannot edit quantities directly

---

## Proposal C: Many2many with Smart View

**Concept:** Computed Many2many + custom tree view with related fields

### Data Model

```python
# In comex.operation
product_ids = fields.Many2many(
    'product.product',
    compute='_compute_product_ids',
    store=True,
    string='Products'
)

@api.depends('purchase_order_ids.order_line.product_id', 'sale_order_ids.order_line.product_id')
def _compute_product_ids(self):
    for operation in self:
        products = self.env['product.product']
        products |= operation.purchase_order_ids.mapped('order_line.product_id')
        products |= operation.sale_order_ids.mapped('order_line.product_id')
        operation.product_ids = products
```

### Custom View (Product Perspective)

```python
# New transient model for view
class ComexProductOperationView(models.TransientModel):
    _name = 'comex.product.operation.view'
    _description = 'Product-Operation View'
    
    product_id = fields.Many2one('product.product')
    operation_ids = fields.Many2many('comex.operation')
    total_qty = fields.Float()
    total_value = fields.Monetary()
    
    @api.model
    def get_lines(self):
        """Generate transient records for view."""
        # Query to aggregate data
        ...
```

### Pros ✅
- ✅ Flexible
- ✅ Can show aggregated data

### Cons ⚠️
- ⚠️ Complex implementation
- ⚠️ No line-level detail (only product aggregates)
- ⚠️ Not suitable for showing order lines

---

## Proposal D: Related Fields in Tree (Simple)

**Concept:** Don't create new model, just improve tree view with related fields

### Implementation

```python
# In comex.operation - Add computed field for tree display
product_summary = fields.Char(
    compute='_compute_product_summary',
    string='Products',
    store=True
)

@api.depends('purchase_order_ids.order_line.product_id')
def _compute_product_summary(self):
    for record in self:
        products = record.purchase_order_ids.mapped('order_line.product_id')
        if products:
            names = products.mapped('display_name')
            record.product_summary = ', '.join(names[:2]) + (f' (+{len(names)-2})' if len(names) > 2 else '')
        else:
            record.product_summary = False
```

### Pros ✅
- ✅ Very simple (~30 lines)
- ✅ No new model needed

### Cons ⚠️
- ❌ Still saturates tree view with tags/text
- ❌ No line-level perspective
- ❌ Doesn't solve the original problem

---

## Comparison Matrix

| Aspect | Proposal A (New Model) | Proposal B (SQL View) | Proposal C (M2M) | Proposal D (Simple) |
|--------|----------------------|---------------------|---------------|------------------|
| **Line-level detail** | ✅ Full | ✅ Full | ❌ Aggregate only | ❌ None |
| **Editable** | ✅ Yes | ❌ Read-only | ❌ No | ❌ No |
| **Data duplication** | ⚠️ Yes | ✅ None | ⚠️ M2M table | ✅ None |
| **Sync complexity** | ⚠️ Medium | ✅ Auto | ⚠️ Medium | ✅ Auto |
| **Performance** | ✅ Good | ✅ Good | ⚠️ Slower | ✅ Good |
| **Code lines** | ~200 | ~100 | ~150 | ~30 |
| **Pattern match** | ✅ OCA PR pattern | ⚠️ Different | ❌ No | ❌ No |
| **Extensibility** | ✅ High | ⚠️ Limited | ⚠️ Medium | ❌ Low |
| **Manual lines** | ✅ Yes | ❌ No | ❌ No | ❌ No |

---

## Recommendations

### Best for Production: **Proposal A** ⭐ RECOMMENDED
**Why:**
- Matches OCA purchase_request pattern exactly
- Full CRUD capability
- Easy to extend with custom fields
- Standard Odoo pattern (header + lines)
- Can add manual lines (not just from POs/SOs)

**Trade-off:** Data duplication, but manageable with proper sync logic

---

### Best for Read-Only: **Proposal B** ⭐⭐
**Why:**
- Zero data duplication
- Always in sync
- Simpler implementation
- Good for reporting/analysis

**Trade-off:** Cannot edit lines directly, requires export feature implementation

---

### Not Recommended: **Proposal C & D**
- **C**: Too complex for the value provided
- **D**: Doesn't solve the original problem

---

## Implementation Estimate

### Proposal A (Full Implementation):
**Files to create/modify:**
1. `models/comex_operation_product_line.py` (~150 lines)
2. `views/comex_operation_product_line_views.xml` (~80 lines)
3. `security/ir.model.access.csv` (1 line)
4. Modify `models/comex_operation.py` (add field + sync method ~50 lines)
5. Add menu entries in `views/comex_operation_menus.xml` (~10 lines)

**Total:** ~290 lines
**Effort:** 3-4 hours

### Proposal B (SQL View):
**Files to create/modify:**
1. `models/comex_operation_product_line.py` (~100 lines - SQL view)
2. `views/comex_operation_product_line_views.xml` (~60 lines)
3. `security/ir.model.access.csv` (1 line)
4. Add menu entry (~10 lines)
5. Add `comex_operation_id` to `sale.order` if exports needed (~10 lines)

**Total:** ~180 lines
**Effort:** 2-3 hours

---

## Next Steps

**Please choose:**
1. **Proposal A** - Full featured model (like OCA pattern)
2. **Proposal B** - Lightweight SQL view (read-only)
3. **Hybrid** - Start with B, add A later if edit needed
4. **Different approach** - Tell me your preference

Once you decide, I'll proceed with full implementation.
