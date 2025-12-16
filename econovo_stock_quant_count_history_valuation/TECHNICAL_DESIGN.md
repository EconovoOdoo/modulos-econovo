# Technical Design Document
## econovo_stock_quant_count_history_valuation

**Version:** 17.0.1.0.0  
**Author:** Jose D. Leonett  
**Date:** 2025-12-16

---

## 1. Overview

This module extends `econovo_stock_quant_count_history` to add cost valuation capabilities, 
allowing users to see the financial impact of inventory counts in both company currency (ARS) 
and USD.

### 1.1 Design Principles

1. **Zero impact on native Odoo code** - Only extend, never modify core behavior
2. **Loose coupling** - Can be uninstalled without affecting base module
3. **Follow OCA patterns** - Use standard Odoo/OCA coding conventions
4. **Use native UI components** - Monetary fields, standard widgets, native grouping
5. **Respect existing valuation logic** - Leverage `stock.valuation.layer` when available

---

## 2. Dependencies Analysis

```
econovo_stock_quant_count_history_valuation
├── econovo_stock_quant_count_history (required)
│   └── stock
├── stock_account (required)
│   ├── stock
│   └── account
└── gg_cost_dolarization (optional - soft dependency)
    ├── product
    └── mrp
```

### 2.1 Handling Optional Dependency (gg_cost_dolarization)

Since `gg_cost_dolarization` provides `standard_price_usd` on products, we need to handle 
cases where it's not installed:

```python
# Pattern: Check field existence at runtime
def _get_unit_cost_usd(self, product, date):
    """Get USD cost, falling back to currency conversion if gg_cost_dolarization not installed."""
    if hasattr(product, 'standard_price_usd') and product.standard_price_usd:
        return product.standard_price_usd
    # Fallback: Convert using res.currency
    return self._convert_to_usd(product.standard_price, date)
```

---

## 3. Data Model

### 3.1 New Model: stock.quant.count.history.valuation

```python
class StockQuantCountHistoryValuation(models.Model):
    _name = 'stock.quant.count.history.valuation'
    _description = 'Count History Valuation'
    _order = 'id desc'

    # === Relationship ===
    history_id = fields.Many2one(
        'stock.quant.count.history',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(related='history_id.company_id', store=True)
    
    # === Currency Configuration ===
    currency_id = fields.Many2one(
        'res.currency',
        string='Company Currency',
        compute='_compute_currencies',
        store=True,
    )
    currency_usd_id = fields.Many2one(
        'res.currency',
        string='USD Currency',
        compute='_compute_currencies',
        store=True,
    )
    exchange_rate = fields.Float(
        string='Exchange Rate (ARS/USD)',
        digits=(16, 6),
        help='Exchange rate at the moment of count',
    )
    
    # === Snapshot Values (at count moment) ===
    snapshot_unit_cost = fields.Monetary(
        string='Unit Cost',
        currency_field='currency_id',
        help='Product cost at the moment of count',
    )
    snapshot_unit_cost_usd = fields.Monetary(
        string='Unit Cost (USD)',
        currency_field='currency_usd_id',
    )
    snapshot_cost_method = fields.Selection([
        ('standard', 'Standard Price'),
        ('fifo', 'FIFO'),
        ('average', 'Average Cost'),
    ], string='Cost Method')
    
    # === Calculated Snapshot Values ===
    snapshot_on_hand_value = fields.Monetary(
        string='On Hand Value',
        currency_field='currency_id',
        compute='_compute_snapshot_values',
        store=True,
    )
    snapshot_counted_value = fields.Monetary(
        string='Counted Value',
        currency_field='currency_id',
        compute='_compute_snapshot_values',
        store=True,
    )
    snapshot_difference_value = fields.Monetary(
        string='Difference Value',
        currency_field='currency_id',
        compute='_compute_snapshot_values',
        store=True,
    )
    snapshot_difference_value_usd = fields.Monetary(
        string='Difference Value (USD)',
        currency_field='currency_usd_id',
        compute='_compute_snapshot_values',
        store=True,
    )
    
    # === SVL Integration (for Applied counts) ===
    valuation_layer_ids = fields.Many2many(
        'stock.valuation.layer',
        string='Valuation Layers',
        readonly=True,
    )
    has_svl = fields.Boolean(
        string='Has Valuation Layers',
        compute='_compute_svl_values',
        store=True,
    )
    svl_total_value = fields.Monetary(
        string='SVL Total Value',
        currency_field='currency_id',
        compute='_compute_svl_values',
        store=True,
    )
    svl_total_value_usd = fields.Monetary(
        string='SVL Total Value (USD)',
        currency_field='currency_usd_id',
        compute='_compute_svl_values',
        store=True,
    )
    
    # === Final Values (SVL if available, else Snapshot) ===
    value_source = fields.Selection([
        ('snapshot', 'Estimated (Snapshot)'),
        ('svl', 'Actual (from Valuation Layer)'),
        ('none', 'No Difference'),
    ], string='Value Source', compute='_compute_final_values', store=True)
    
    final_difference_value = fields.Monetary(
        string='Final Difference Value',
        currency_field='currency_id',
        compute='_compute_final_values',
        store=True,
    )
    final_difference_value_usd = fields.Monetary(
        string='Final Difference Value (USD)',
        currency_field='currency_usd_id',
        compute='_compute_final_values',
        store=True,
    )
    is_loss = fields.Boolean(
        string='Is Loss',
        compute='_compute_final_values',
        store=True,
    )
```

### 3.2 Extension: stock.quant.count.history

```python
class StockQuantCountHistory(models.Model):
    _inherit = 'stock.quant.count.history'
    
    valuation_id = fields.One2many(
        'stock.quant.count.history.valuation',
        'history_id',
        string='Valuation',
    )
    
    # Delegate fields for easy access in views
    final_difference_value = fields.Monetary(
        related='valuation_id.final_difference_value',
        string='Difference Value',
    )
    final_difference_value_usd = fields.Monetary(
        related='valuation_id.final_difference_value_usd',
        string='Difference Value (USD)',
    )
    is_loss = fields.Boolean(related='valuation_id.is_loss')
```

---

## 4. Edge Cases Analysis

### 4.1 Cost Method Edge Cases

| Case | Scenario | Handling |
|------|----------|----------|
| EC-1 | Product has no cost (standard_price = 0) | Store 0, show warning badge |
| EC-2 | Product cost changed after count | Snapshot preserves original cost |
| EC-3 | FIFO product with multiple layers | Use avg from remaining_qty/remaining_value |
| EC-4 | AVCO recalculation | SVL provides accurate value |
| EC-5 | Cost method changed after count | Snapshot preserves original method |

### 4.2 Currency Edge Cases

| Case | Scenario | Handling |
|------|----------|----------|
| EC-6 | No USD rate for count date | Use nearest previous rate |
| EC-7 | No USD rate exists at all | Fallback rate = 1.0, show warning |
| EC-8 | Company currency is already USD | Skip conversion, same values |
| EC-9 | Multi-company with different currencies | Each company uses its own currency |
| EC-10 | gg_cost_dolarization not installed | Calculate USD via res.currency |

### 4.3 SVL Edge Cases

| Case | Scenario | Handling |
|------|----------|----------|
| EC-11 | Count "Saved" (no adjustment) | No SVL, use snapshot only |
| EC-12 | Count "Applied" with diff = 0 | No SVL created, use snapshot |
| EC-13 | Multiple SVL for same adjustment | Sum all related SVL values |
| EC-14 | SVL deleted/modified after count | Stored computed values remain |
| EC-15 | Quant deleted after count | valuation still valid (ondelete='cascade' on history) |

### 4.4 Product Edge Cases

| Case | Scenario | Handling |
|------|----------|----------|
| EC-16 | Consumable product (no valuation) | Show snapshot, no SVL possible |
| EC-17 | Service product | Should not appear in inventory counts |
| EC-18 | Product archived after count | Valuation remains valid |
| EC-19 | Serial tracked product (qty=1) | Normal handling, max diff = ±1 |
| EC-20 | Lot tracked product | Normal handling |

### 4.5 Timing Edge Cases

| Case | Scenario | Handling |
|------|----------|----------|
| EC-21 | Count at midnight (date boundary) | Use count_datetime for rate lookup |
| EC-22 | Count backdated (accounting_date) | Use accounting_date if set |
| EC-23 | SVL created later (async) | Recompute on demand |

---

## 5. Implementation Flow

### 5.1 Valuation Creation Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                    VALUATION CREATION FLOW                           │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  stock.quant.count.history CREATED                                   │
│            │                                                          │
│            ▼                                                          │
│  ┌─────────────────────────────────────────┐                         │
│  │  @api.model_create_multi                │                         │
│  │  def create(vals_list):                 │                         │
│  │      records = super().create(...)      │                         │
│  │      records._create_valuation()        │◄── Auto-create          │
│  │      return records                     │    valuation record     │
│  └─────────────────────────────────────────┘                         │
│            │                                                          │
│            ▼                                                          │
│  ┌─────────────────────────────────────────┐                         │
│  │  def _create_valuation(self):           │                         │
│  │      1. Get product cost                │                         │
│  │      2. Get exchange rate               │                         │
│  │      3. Get cost method                 │                         │
│  │      4. Create valuation record         │                         │
│  └─────────────────────────────────────────┘                         │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

### 5.2 SVL Linking Flow (for Applied counts)

```
┌──────────────────────────────────────────────────────────────────────┐
│                      SVL LINKING FLOW                                 │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  action_apply_inventory() called on stock.quant                      │
│            │                                                          │
│            ▼                                                          │
│  ┌─────────────────────────────────────────┐                         │
│  │  stock.move created                     │                         │
│  │  stock.move._action_done()              │                         │
│  │      → stock.valuation.layer created    │                         │
│  └─────────────────────────────────────────┘                         │
│            │                                                          │
│            ▼                                                          │
│  ┌─────────────────────────────────────────┐                         │
│  │  stock.quant.count.history              │                         │
│  │  (already created with state='applied') │                         │
│  │                                          │                         │
│  │  def _link_valuation_layers(self):      │◄── Called post-apply    │
│  │      # Find SVL by:                      │                         │
│  │      # - product_id                      │                         │
│  │      # - create_date ~ count_datetime    │                         │
│  │      # - quantity = difference           │                         │
│  └─────────────────────────────────────────┘                         │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

### 5.3 Strategy: Finding Related SVL

The challenge is linking the count history to the SVL created by the adjustment. 
We cannot modify `stock.valuation.layer` to add a direct link (would require schema change).

**Strategy: Match by correlation**

```python
def _find_related_svl(self):
    """Find SVL records that match this count's adjustment."""
    self.ensure_one()
    if not self.history_id.was_applied or self.history_id.difference == 0:
        return self.env['stock.valuation.layer']
    
    # Time window: SVL created within 5 minutes of count
    time_from = self.history_id.count_datetime - timedelta(minutes=5)
    time_to = self.history_id.count_datetime + timedelta(minutes=5)
    
    domain = [
        ('product_id', '=', self.history_id.product_id.id),
        ('company_id', '=', self.history_id.company_id.id),
        ('create_date', '>=', time_from),
        ('create_date', '<=', time_to),
        # Match quantity (negative for decrease, positive for increase)
        ('quantity', '=', self.history_id.difference),
    ]
    
    # Additional filter: description contains inventory adjustment reference
    svl = self.env['stock.valuation.layer'].search(domain, limit=1)
    return svl
```

**Alternative Strategy: Context propagation**

Pass count_history_id through context during apply:

```python
# In econovo_stock_quant_count_history.models.stock_quant
def action_apply_inventory(self):
    # ... existing code ...
    # Add context with history IDs
    ctx = dict(self.env.context, count_history_ids=history_records.ids)
    self.with_context(ctx)._apply_inventory()

# In econovo_stock_quant_count_history_valuation.models.stock_valuation_layer
class StockValuationLayer(models.Model):
    _inherit = 'stock.valuation.layer'
    
    count_history_id = fields.Many2one(
        'stock.quant.count.history',
        string='Count History',
        readonly=True,
        index=True,
    )
    
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        # Link to count history if in context
        if self.env.context.get('count_history_ids'):
            # Match and link...
        return records
```

**Recommended: Hybrid approach**
- Add `count_history_id` field to SVL
- Set during apply via context
- Fallback to correlation matching for historical data

---

## 6. View Design

### 6.1 Count History Tree View (Extended)

```xml
<!-- Columns added to existing tree -->
<xpath expr="//field[@name='state']" position="after">
    <field name="final_difference_value" 
           decoration-danger="is_loss" 
           decoration-success="not is_loss and final_difference_value != 0"
           optional="show"/>
    <field name="final_difference_value_usd" 
           decoration-danger="is_loss" 
           decoration-success="not is_loss and final_difference_value_usd != 0"
           optional="show"/>
</xpath>
```

### 6.2 Count History Form View - Valuation Tab

```xml
<page string="Valuation" name="valuation">
    <group>
        <group string="Cost at Count Moment">
            <field name="snapshot_cost_method" readonly="1"/>
            <label for="snapshot_unit_cost"/>
            <div class="o_row">
                <field name="snapshot_unit_cost" nolabel="1"/>
                <field name="snapshot_unit_cost_usd" nolabel="1"/>
            </div>
        </group>
        <group string="Exchange Rate">
            <field name="exchange_rate"/>
            <field name="currency_id" invisible="1"/>
            <field name="currency_usd_id" invisible="1"/>
        </group>
    </group>
    
    <group string="Valuation Summary" class="oe_title">
        <group>
            <field name="snapshot_on_hand_value"/>
            <field name="snapshot_counted_value"/>
            <field name="snapshot_difference_value" 
                   decoration-danger="snapshot_difference_value &lt; 0"
                   decoration-success="snapshot_difference_value &gt; 0"/>
        </group>
        <group>
            <field name="snapshot_difference_value_usd"
                   decoration-danger="snapshot_difference_value_usd &lt; 0"
                   decoration-success="snapshot_difference_value_usd &gt; 0"/>
        </group>
    </group>
    
    <group string="Valuation Layers" invisible="not has_svl">
        <field name="valuation_layer_ids" nolabel="1" readonly="1">
            <tree>
                <field name="create_date"/>
                <field name="quantity"/>
                <field name="unit_cost"/>
                <field name="value"/>
            </tree>
        </field>
        <group>
            <field name="svl_total_value"/>
            <field name="svl_total_value_usd"/>
        </group>
    </group>
    
    <group string="Final Impact" class="oe_title">
        <field name="value_source"/>
        <label for="final_difference_value"/>
        <div class="o_row">
            <field name="final_difference_value" 
                   class="oe_inline"
                   decoration-danger="is_loss"
                   decoration-success="not is_loss and final_difference_value != 0"/>
            <span class="badge bg-danger" invisible="not is_loss">Loss</span>
            <span class="badge bg-success" 
                  invisible="is_loss or final_difference_value == 0">Gain</span>
        </div>
        <field name="final_difference_value_usd"
               decoration-danger="is_loss"
               decoration-success="not is_loss"/>
    </group>
</page>
```

### 6.3 Search View Extensions

```xml
<filter string="With Loss" name="with_loss" 
        domain="[('is_loss', '=', True)]"/>
<filter string="With Gain" name="with_gain" 
        domain="[('is_loss', '=', False), ('final_difference_value', '!=', 0)]"/>

<group expand="0" string="Group By">
    <filter string="Value Source" name="group_value_source" 
            context="{'group_by': 'value_source'}"/>
</group>
```

---

## 7. Testing Strategy

### 7.1 Unit Tests

```python
class TestCountHistoryValuation(TransactionCase):
    
    def test_valuation_created_with_history(self):
        """Valuation record created automatically with count history."""
        
    def test_snapshot_cost_captured(self):
        """Snapshot captures product cost at count moment."""
        
    def test_exchange_rate_captured(self):
        """Exchange rate captured from res.currency.rate."""
        
    def test_no_usd_rate_fallback(self):
        """Fallback to rate=1 when no USD rate exists."""
        
    def test_svl_linked_on_apply(self):
        """SVL linked when count is applied."""
        
    def test_saved_count_no_svl(self):
        """Saved count has no SVL, uses snapshot."""
        
    def test_zero_difference_no_svl(self):
        """Zero difference count has no SVL."""
        
    def test_product_no_cost(self):
        """Product with zero cost handled gracefully."""
        
    def test_consumable_product(self):
        """Consumable product has snapshot only."""
        
    def test_fifo_product_svl_value(self):
        """FIFO product uses actual SVL value."""
        
    def test_multi_company_currency(self):
        """Multi-company uses correct company currency."""
```

---

## 8. Security

### 8.1 Access Rights

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_stock_quant_count_history_valuation_user,stock.quant.count.history.valuation.user,model_stock_quant_count_history_valuation,stock.group_stock_user,1,0,0,0
access_stock_quant_count_history_valuation_manager,stock.quant.count.history.valuation.manager,model_stock_quant_count_history_valuation,stock.group_stock_manager,1,1,1,1
```

### 8.2 Record Rules

```xml
<record id="stock_quant_count_history_valuation_rule_company" model="ir.rule">
    <field name="name">Count History Valuation: Company Rule</field>
    <field name="model_id" ref="model_stock_quant_count_history_valuation"/>
    <field name="domain_force">
        ['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]
    </field>
</record>
```

---

## 9. Performance Considerations

1. **Batch valuation creation** - Use `@api.model_create_multi` pattern
2. **Store computed fields** - All monetary fields are stored to avoid recomputation
3. **Index foreign keys** - `history_id`, `company_id` indexed
4. **Lazy SVL linking** - Only search for SVL when needed
5. **Exchange rate caching** - Cache rate lookups within batch operations

---

## 10. Migration Notes

For existing `stock.quant.count.history` records (before this module):

```python
def _post_init_hook(env):
    """Create valuation records for existing count history."""
    histories = env['stock.quant.count.history'].search([
        ('valuation_id', '=', False)
    ])
    for history in histories:
        history._create_valuation()
```

---

## 11. Future Enhancements

1. **Dashboard** - KPI cards showing total losses/gains by period
2. **Reports** - Excel export with valuation summary
3. **Alerts** - Notify when losses exceed threshold
4. **Audit trail** - Track valuation recalculations
