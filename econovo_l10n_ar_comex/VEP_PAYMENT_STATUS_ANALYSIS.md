# Additional Fields Analysis: VEP Amount & Payment Status

## 1. Monto VEP - Investigation & Analysis

### What is VEP (Argentina Context)?

**VEP = Volante Electrónico de Pago** (Electronic Payment Voucher)

**Context:**
- Sistema de AFIP/ARCA (Argentina tax authority)
- Used for paying taxes and customs duties electronically
- Generates a unique payment code (VEP number)
- Required for:
  - **Import duties** (Derechos de Importación)
  - **Customs clearance payments** (Despachos de Aduana)
  - **VAT on imports**
  - **Internal taxes**
  - **Perceptions and withholdings**

### How VEP Works in COMEX Import Flow

```
1. Customs Clearance Created (DI - Despacho de Importación)
   ↓
2. ARCA System calculates tributes (DIE, VAT, Statistics, etc.)
   ↓
3. Generate VEP online (via AFIP portal)
   - Total amount: Sum of all tributes
   - VEP Code: Unique identifier (e.g., 12345678901234567890)
   - Due date: Usually 24-48 hours
   ↓
4. Pay VEP at bank (Banco de la Nación, etc.)
   ↓
5. Payment registered in ARCA system
   ↓
6. Merchandise released from fiscal warehouse
```

### VEP in Current System

Looking at existing `comex.customs.clearance` model:

```python
# Tributes (all in ARS) - These make up the VEP amount
amount_duties = fields.Monetary()        # DIE (Derecho Importación)
amount_statistics = fields.Monetary()   # Estadística (3%)
amount_vat = fields.Monetary()          # IVA (21%)
amount_vat_additional = fields.Monetary()
amount_income_tax = fields.Monetary()   # Percepción Ganancias
amount_gross_income = fields.Monetary() # Percepción IIBB
amount_total = fields.Monetary()        # TOTAL = VEP AMOUNT
```

**KEY INSIGHT:** `amount_total` in customs_clearance IS the VEP amount!

---

## Implementation Proposals for VEP Amount

### Proposal A: Related Field from Customs Clearance ⭐ RECOMMENDED

**Concept:** Use existing `amount_total` from customs clearances

```python
# In comex.operation
vep_amount = fields.Monetary(
    string='VEP Amount',
    compute='_compute_vep_amount',
    store=True,
    currency_field='currency_ars_id',
    help='Total VEP (Volante Electrónico de Pago) amount for customs duties. Sum of all customs clearance tributes.'
)

currency_ars_id = fields.Many2one(
    'res.currency',
    string='ARS Currency',
    default=lambda self: self.env.ref('base.ARS', raise_if_not_found=False),
)

@api.depends('customs_clearance_ids.amount_total')
def _compute_vep_amount(self):
    """Sum all customs clearance tributes (VEP amounts)."""
    for record in self:
        record.vep_amount = sum(record.customs_clearance_ids.mapped('amount_total'))
```

**Display in Tree/Form:**
```xml
<!-- Tree view -->
<field name="vep_amount" optional="show" widget="monetary"/>

<!-- Form view - Financial page -->
<group name="customs_amounts" string="Customs Duties (ARS)">
    <field name="currency_ars_id" invisible="1"/>
    <field name="vep_amount" widget="monetary"/>
</group>
```

**Pros:**
- ✅ Uses existing data (no duplication)
- ✅ Always in sync
- ✅ Correct currency (ARS - tributes are always in pesos)
- ✅ Simple implementation (~20 lines)

**Cons:**
- ⚠️ Only shows sum (not individual VEP codes)
- ⚠️ If multiple clearances, shows total of all VEPs

---

### Proposal B: One2many to VEP Detail Model

**Concept:** Create separate model for VEP tracking

```python
class ComexVEP(models.Model):
    _name = 'comex.vep'
    _description = 'COMEX VEP (Volante Electrónico de Pago)'
    
    operation_id = fields.Many2one('comex.operation', required=True)
    customs_clearance_id = fields.Many2one('comex.customs.clearance')
    
    # VEP details
    vep_code = fields.Char(string='VEP Code', help='20-digit VEP code from AFIP')
    vep_amount = fields.Monetary(currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.ref('base.ARS'))
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('generated', 'Generated'),
        ('paid', 'Paid'),
        ('expired', 'Expired'),
    ])
    
    date_generated = fields.Date()
    date_due = fields.Date()
    date_paid = fields.Date()
```

**Pros:**
- ✅ Detailed tracking (individual VEPs)
- ✅ Can track VEP codes and status
- ✅ Payment tracking

**Cons:**
- ⚠️ More complex (~100 lines)
- ⚠️ User might not have VEP codes (sometimes paid directly)
- ⚠️ Overkill if only need total amount

---

### Proposal C: Manual Field in Operation

**Concept:** Simple monetary field for manual entry

```python
vep_amount = fields.Monetary(
    string='VEP Amount (ARS)',
    currency_field='currency_ars_id',
    help='Total VEP amount for customs duties payment'
)
```

**Pros:**
- ✅ Very simple
- ✅ User can enter expected amount before clearance

**Cons:**
- ❌ Manual entry (error-prone)
- ❌ Not synchronized with actual tributes
- ❌ Data duplication

---

### VEP Recommendation: **Proposal A** ⭐

**Justification:**
- VEP amount = Total tributes in customs clearance
- Already calculated in `comex.customs.clearance.amount_total`
- Just need computed field to sum all clearances
- Simple, accurate, always in sync

**Display in tree view:**
```
Operation | Partner | VEP Amount  | ETD        | ...
----------|---------|-------------|------------|----
IMP001    | Supp A  | $ 4,050,000 | 2026-01-15 | ...
IMP002    | Supp B  | $ 2,300,000 | 2026-01-20 | ...
```

---

## 2. Payment Status - Analysis & Implementation

### Business Context

**Question:** What does "payment status" mean for COMEX operation?

**Possible interpretations:**
1. **Invoices paid?** (Commercial invoices to supplier)
2. **VEP paid?** (Customs duties to ARCA)
3. **All payments?** (Invoices + VEP + fees + freight)
4. **MULC status?** (Foreign exchange payments)

**Most likely:** Status of ALL financial obligations (invoices + tributes)

---

## Payment Status Proposals

### Proposal A: Computed from Invoices + Clearances ⭐ RECOMMENDED

**Concept:** Calculate status based on all financial documents

```python
class ComexOperation(models.Model):
    _name = 'comex.operation'
    
    payment_status = fields.Selection(
        selection=[
            ('not_paid', 'Not Paid'),
            ('partial', 'Partially Paid'),
            ('paid', 'Paid'),
            ('overpaid', 'Overpaid'),
        ],
        string='Payment Status',
        compute='_compute_payment_status',
        store=True,
    )
    
    # Financial amounts
    total_invoice_amount = fields.Monetary(
        compute='_compute_financial_totals',
        store=True,
    )
    total_paid_amount = fields.Monetary(
        compute='_compute_financial_totals',
        store=True,
    )
    total_due_amount = fields.Monetary(
        compute='_compute_financial_totals',
        store=True,
    )
    
    @api.depends(
        'invoice_ids.amount_total',
        'invoice_ids.amount_residual',
        'invoice_ids.payment_state',
    )
    def _compute_financial_totals(self):
        """Calculate total amounts from all invoices."""
        for record in self:
            invoices = record.invoice_ids.filtered(lambda inv: inv.state == 'posted')
            
            # Total invoiced
            record.total_invoice_amount = sum(invoices.mapped('amount_total'))
            
            # Total paid (invoiced - residual)
            record.total_paid_amount = sum(
                inv.amount_total - inv.amount_residual for inv in invoices
            )
            
            # Total due (still owed)
            record.total_due_amount = sum(invoices.mapped('amount_residual'))
    
    @api.depends('total_invoice_amount', 'total_paid_amount', 'total_due_amount')
    def _compute_payment_status(self):
        """Determine overall payment status."""
        for record in self:
            if record.total_invoice_amount == 0:
                record.payment_status = 'not_paid'
            elif record.total_due_amount == 0:
                record.payment_status = 'paid'
            elif record.total_paid_amount == 0:
                record.payment_status = 'not_paid'
            elif record.total_due_amount < 0:
                record.payment_status = 'overpaid'
            else:
                record.payment_status = 'partial'
```

**Tree View Display:**
```xml
<tree decoration-success="payment_status == 'paid'"
      decoration-warning="payment_status == 'partial'"
      decoration-danger="payment_status == 'not_paid'">
    <field name="name"/>
    <field name="partner_id"/>
    <field name="total_invoice_amount" widget="monetary"/>
    <field name="total_paid_amount" widget="monetary"/>
    <field name="total_due_amount" widget="monetary"/>
    <field name="payment_status" widget="badge"
           decoration-success="payment_status == 'paid'"
           decoration-warning="payment_status == 'partial'"
           decoration-danger="payment_status == 'not_paid'"
           decoration-info="payment_status == 'overpaid'"/>
</tree>
```

**Visual Example:**
```
Operation | Total       | Paid        | Due         | Status
----------|-------------|-------------|-------------|----------
IMP001    | $100,000.00 | $100,000.00 | $0.00       | 🟢 Paid
IMP002    | $50,000.00  | $25,000.00  | $25,000.00  | 🟡 Partial
IMP003    | $75,000.00  | $0.00       | $75,000.00  | 🔴 Not Paid
```

**Pros:**
- ✅ Accurate (based on actual invoice payment state)
- ✅ Standard Odoo pattern (uses `amount_residual`)
- ✅ Auto-updates when payments recorded
- ✅ Visual indicators (badges, colors)
- ✅ Shows detailed amounts (total, paid, due)

**Cons:**
- ⚠️ Only tracks invoices (not MULC or other obligations)
- ⚠️ ~60 lines of code

---

### Proposal B: Extended Payment Status (Invoices + VEP + MULC)

**Concept:** Comprehensive status including all payment types

```python
payment_status_commercial = fields.Selection(...)  # Supplier invoices
payment_status_customs = fields.Selection(...)     # VEP/Tributes
payment_status_forex = fields.Selection(...)       # MULC payments

payment_status_overall = fields.Selection(
    compute='_compute_payment_status_overall',
    help='Overall status: Paid only if ALL are paid'
)

@api.depends('payment_status_commercial', 'payment_status_customs', 'payment_status_forex')
def _compute_payment_status_overall(self):
    for record in self:
        statuses = [
            record.payment_status_commercial,
            record.payment_status_customs,
            record.payment_status_forex,
        ]
        
        if all(s == 'paid' for s in statuses):
            record.payment_status_overall = 'paid'
        elif any(s == 'not_paid' for s in statuses):
            record.payment_status_overall = 'partial'
        else:
            record.payment_status_overall = 'partial'
```

**Display:**
```
Operation | Commercial | Customs | Forex | Overall
----------|------------|---------|-------|--------
IMP001    | 🟢 Paid    | 🟢 Paid | 🟢 Paid | 🟢 Paid
IMP002    | 🟡 Partial | 🔴 Not  | 🟢 Paid | 🔴 Partial
```

**Pros:**
- ✅ Comprehensive view
- ✅ Distinguishes payment types

**Cons:**
- ⚠️ More complex (~100 lines)
- ⚠️ Might be too detailed for tree view

---

### Proposal C: Simple Badge from Invoice States

**Concept:** Just aggregate invoice payment_state

```python
payment_status = fields.Selection(
    selection=[
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid'),
        ('partial', 'Partial'),
        ('reversed', 'Reversed'),
    ],
    compute='_compute_payment_status',
)

@api.depends('invoice_ids.payment_state')
def _compute_payment_status(self):
    for record in self:
        invoice_states = record.invoice_ids.mapped('payment_state')
        
        if not invoice_states:
            record.payment_status = 'not_paid'
        elif all(s == 'paid' for s in invoice_states):
            record.payment_status = 'paid'
        elif all(s == 'not_paid' for s in invoice_states):
            record.payment_status = 'not_paid'
        else:
            record.payment_status = 'partial'
```

**Pros:**
- ✅ Very simple (~20 lines)
- ✅ Uses native Odoo payment_state

**Cons:**
- ⚠️ Less granular (no amounts shown)
- ⚠️ Doesn't distinguish invoice types

---

## Payment Status Recommendation: **Proposal A** ⭐

**Justification:**
- Shows both status (badge) AND amounts (total/paid/due)
- Standard Odoo pattern (amount_residual)
- Visual indicators for quick scanning
- Detailed enough without being overwhelming
- Extendable (can add customs/forex later if needed)

---

## Combined Implementation Summary

### Fields to Add to `comex.operation`:

**VEP Amount:**
```python
currency_ars_id = fields.Many2one('res.currency', default=lambda self: self.env.ref('base.ARS'))
vep_amount = fields.Monetary(
    compute='_compute_vep_amount',
    store=True,
    currency_field='currency_ars_id',
)
```

**Payment Status:**
```python
total_invoice_amount = fields.Monetary(compute='_compute_financial_totals', store=True)
total_paid_amount = fields.Monetary(compute='_compute_financial_totals', store=True)
total_due_amount = fields.Monetary(compute='_compute_financial_totals', store=True)
payment_status = fields.Selection([...], compute='_compute_payment_status', store=True)
```

**Compute Methods:**
```python
@api.depends('customs_clearance_ids.amount_total')
def _compute_vep_amount(self): ...

@api.depends('invoice_ids.amount_total', 'invoice_ids.amount_residual')
def _compute_financial_totals(self): ...

@api.depends('total_invoice_amount', 'total_paid_amount', 'total_due_amount')
def _compute_payment_status(self): ...
```

**Tree View Updates:**
```xml
<field name="vep_amount" optional="show"/>
<field name="total_invoice_amount" optional="show"/>
<field name="total_paid_amount" optional="show"/>
<field name="total_due_amount" optional="show"/>
<field name="payment_status" widget="badge" optional="show"/>
```

**Estimated:** ~120 lines total, 1-2 hours

---

## Questions for User

1. **VEP Amount:**
   - ✅ Confirm: VEP = Sum of customs clearance tributes?
   - ❓ Need individual VEP codes tracked, or just total amount?
   - ❓ Show in tree view or just form view?

2. **Payment Status:**
   - ✅ Confirm: Status of supplier invoices + customs duties?
   - ❓ Include MULC payment status?
   - ❓ Show detailed amounts (total/paid/due) or just badge?
   - ❓ Need separate status for commercial vs customs payments?

3. **Priority:**
   - Implement VEP first or Payment Status first?
   - Or both together?

---

**Next Steps:**
Once you confirm the approach, I'll implement both fields with full code, views, and tests.
