# Phase 4.1: Tax Groups Implementation Plan
## Alternativa 5 - Automatic Tax Calculation

**Date:** February 4, 2026  
**Module:** econovo_l10n_ar_comex  
**Strategy:** Tax Groups for automatic calculation of all import tributes

---

## 🎯 OBJECTIVE

Implement automatic calculation of ALL import tributes (VAT, IIGG, IIBB) using Odoo's native tax group mechanism, eliminating manual product mappings for calculated taxes.

---

## 📊 CURRENT STATE ANALYSIS

### Existing Components

**✅ Working:**
- Customs clearance model with all tribute fields
- Product mappings system (comex.tribute.product.mapping)
- Keyword mappings for parsing vendor bills
- Invoice creation action (action_create_tribute_invoice)
- Parse logging and audit trail

**❌ Issues:**
- Mapping VAT as product (should be automatic tax)
- Mapping percepciones as products (should be automatic taxes)
- Manual calculation required for each tax
- Not following Odoo native patterns
- Not using Argentina localization tax infrastructure

### Current Product Mappings (to be modified)

```
✅ KEEP: amount_duties → Product DIE
✅ KEEP: amount_statistics → Product Statistics Fee
✅ KEEP: amount_fees → Product Other Fees
❌ REMOVE: amount_vat → (becomes automatic)
❌ REMOVE: amount_vat_additional → (becomes automatic)
❌ REMOVE: amount_income_tax → (becomes automatic)
❌ REMOVE: amount_gross_income → (becomes automatic)
❌ REMOVE: amount_taxes → (becomes automatic or keep for misc)
```

---

## 🏗️ ARCHITECTURE DESIGN

### Tax Structure

```
┌─────────────────────────────────────────────┐
│   Tax Group: Import Tributes               │
│   (comex_tax_group_import_tributes)        │
├─────────────────────────────────────────────┤
│   Children:                                 │
│   ├─ IVA Import 21% (account.tax)         │
│   ├─ Percepción IIGG 6% (account.tax)     │
│   └─ Percepción IIBB 3% (account.tax)     │
└─────────────────────────────────────────────┘
```

### Product Configuration

```python
Product: DIE - Import Duties
├─ Type: Service
├─ Purchase: True
├─ Supplier Taxes: [comex_tax_group_import_tributes]
└─ Account: Configurable (default: Customs Duties expense)

Product: Statistics Fee
├─ Type: Service
├─ Purchase: True
├─ Supplier Taxes: [comex_tax_group_import_tributes]
└─ Account: Configurable (default: Customs Fees expense)

Product: Other Fees
├─ Type: Service
├─ Purchase: True
├─ Supplier Taxes: [comex_tax_group_import_tributes] or []
└─ Account: Configurable (default: Other expenses)
```

### Invoice Generation Flow

```
Customs Clearance
├─ amount_duties = $1000        ──┐
├─ amount_statistics = $300     ──┤ Mapped to products
├─ amount_fees = $100           ──┘
│
├─ amount_vat = $294            ──┐
├─ amount_income_tax = $84      ──┤ Validation only
└─ amount_gross_income = $42    ──┘

↓ action_create_tribute_invoice()

Invoice Lines:
1. DIE: $1000
   ├─ IVA 21%: $210
   ├─ Perc IIGG 6%: $60
   └─ Perc IIBB 3%: $30
   Subtotal: $1,300

2. Statistics: $300
   ├─ IVA 21%: $63
   ├─ Perc IIGG 6%: $18
   └─ Perc IIBB 3%: $9
   Subtotal: $390

3. Fees: $100
   (no taxes)
   Subtotal: $100

TOTAL: $1,790

↓ Validation

Compare:
- Calculated VAT ($273) vs amount_vat ($294)
- Calculated IIGG ($78) vs amount_income_tax ($84)
- Calculated IIBB ($39) vs amount_gross_income ($42)

If difference > threshold → Warning/Block
```

---

## 📝 IMPLEMENTATION TASKS

### Task 1: Create Tax Infrastructure
**Files:** `data/comex_tax_data.xml` (NEW)

**Components:**
1. Tax: IVA Importación 21%
2. Tax: Percepción IIGG (configurable %, default 6%)
3. Tax: Percepción IIBB (configurable %, default 3%)
4. Tax Group: Tributos Importación

**Considerations:**
- Check if Argentina localization already has these taxes
- Make percepciones configurable per company
- Set correct tax accounts (from chart of accounts)
- Type: purchase (supplier taxes)
- Invoice repartition: Base + Tax lines

### Task 2: Update Product Definitions
**Files:** `data/comex_tribute_products_data.xml`

**Changes:**
```xml
<!-- BEFORE -->
<field name="supplier_taxes_id" eval="False"/>

<!-- AFTER -->
<field name="supplier_taxes_id" eval="[(6, 0, [ref('comex_tax_group_import_tributes')])]"/>
```

**Products to update:**
- product_comex_die
- product_comex_statistics
- product_comex_tariff (if used)

**Products to keep without tax:**
- product_comex_guard_service (fees, no tax)

### Task 3: Remove Tax Product Mappings
**Files:** `data/comex_tribute_products_data.xml`

**Remove mappings for:**
- ❌ product_comex_vat (IVA - now automatic)
- ❌ product_comex_perc_iigg (Perc IIGG - now automatic)
- ❌ product_comex_perc_iibb (Perc IIBB - now automatic)

**Keep only:**
- ✅ DIE mapping
- ✅ Statistics mapping
- ✅ Fees mapping

### Task 4: Update Tribute Field Definitions
**Files:** `data/comex_tribute_fields_data.xml`

**Keep all fields** (they become validation fields):
- amount_duties (mapped)
- amount_statistics (mapped)
- amount_vat (validation only)
- amount_vat_additional (validation only)
- amount_income_tax (validation only)
- amount_gross_income (validation only)
- amount_fees (mapped)
- amount_taxes (optional mapping or validation)

### Task 5: Modify Invoice Creation Logic
**Files:** `models/comex_customs_clearance.py`

**Changes in _prepare_tribute_invoice_lines():**

```python
def _prepare_tribute_invoice_lines(self):
    """Prepare invoice lines with automatic tax calculation."""
    lines = []
    
    # Get mappings for BASE AMOUNTS ONLY
    field_to_product = self._get_tribute_product_mappings()
    
    # Fields to map as products (base imponible)
    mappable_fields = [
        'amount_duties',
        'amount_statistics', 
        'amount_fees',
    ]
    
    for field_name in mappable_fields:
        amount = getattr(self, field_name, 0)
        if amount <= 0:
            continue
            
        product = field_to_product.get(field_name)
        if not product:
            _logger.warning(f"No product mapping for {field_name}")
            continue
        
        line_vals = {
            'product_id': product.id,
            'name': product.name,
            'quantity': 1,
            'price_unit': amount,
            # Taxes are automatic from product.supplier_taxes_id
        }
        lines.append((0, 0, line_vals))
    
    return lines
```

### Task 6: Add Tax Validation
**Files:** `models/comex_customs_clearance.py`

**New method:**

```python
def _validate_invoice_taxes(self, invoice):
    """
    Validate that calculated taxes match declared amounts.
    Raises warning if difference exceeds threshold.
    """
    threshold = 1.0  # $1 tolerance
    
    # Calculate totals per tax
    calculated_vat = sum(
        line.price_total - line.price_subtotal
        for line in invoice.line_ids
        if any(t.name == 'IVA Importación 21%' for t in line.tax_ids)
    )
    
    calculated_iigg = sum(
        line.price_total - line.price_subtotal
        for line in invoice.line_ids
        if any('IIGG' in t.name for t in line.tax_ids)
    )
    
    calculated_iibb = sum(
        line.price_total - line.price_subtotal
        for line in invoice.line_ids
        if any('IIBB' in t.name for t in line.tax_ids)
    )
    
    # Compare with declared amounts
    errors = []
    
    if abs(calculated_vat - self.amount_vat) > threshold:
        errors.append(_(
            'VAT mismatch: Calculated $%.2f vs Declared $%.2f'
        ) % (calculated_vat, self.amount_vat))
    
    if abs(calculated_iigg - self.amount_income_tax) > threshold:
        errors.append(_(
            'IIGG mismatch: Calculated $%.2f vs Declared $%.2f'
        ) % (calculated_iigg, self.amount_income_tax))
    
    if abs(calculated_iibb - self.amount_gross_income) > threshold:
        errors.append(_(
            'IIBB mismatch: Calculated $%.2f vs Declared $%.2f'
        ) % (calculated_iibb, self.amount_gross_income))
    
    if errors:
        message = _('Tax validation warnings:\n') + '\n'.join(errors)
        invoice.message_post(body=message, message_type='comment')
        # Optionally raise UserError to block
```

### Task 7: Update Field Help Text
**Files:** `models/comex_customs_clearance.py`

**Update help text to indicate validation purpose:**

```python
amount_vat = fields.Monetary(
    string="VAT",
    help="Import VAT for validation. Actual VAT is calculated automatically "
         "from product taxes (21% on base amounts).",
)

amount_income_tax = fields.Monetary(
    string="Income Tax Perception",
    help="Percepción IIGG for validation. Actual perception is calculated "
         "automatically from product taxes (6% on base amounts).",
)

amount_gross_income = fields.Monetary(
    string="Gross Income Perception",
    help="Percepción IIBB for validation. Actual perception is calculated "
         "automatically from product taxes (3% on base amounts).",
)
```

### Task 8: Update Configuration Settings
**Files:** `views/res_config_settings_views.xml`

**Add settings for:**
- Tax validation tolerance (default 1.0)
- Tax validation mode (warning/block/disabled)
- Default tax percentages (IIGG %, IIBB %)

### Task 9: Update Documentation
**Files:** 
- `README.md`
- User manual

**Document:**
- New tax-based architecture
- How to configure tax percentages
- Validation process
- Troubleshooting tax mismatches

---

## 🧪 TESTING STRATEGY

### Test Cases

**TC1: Basic Invoice Creation**
```
Given: Clearance with amount_duties = $1000
When: Create tribute invoice
Then: 
  - Invoice has 1 line (DIE)
  - Line amount = $1000
  - IVA tax = $210 (21%)
  - IIGG tax = $60 (6%)
  - IIBB tax = $30 (3%)
  - Total = $1300
```

**TC2: Multiple Products**
```
Given: 
  - amount_duties = $1000
  - amount_statistics = $300
  - amount_fees = $100
When: Create tribute invoice
Then:
  - 3 invoice lines
  - DIE: $1000 + taxes = $1300
  - Stats: $300 + taxes = $390
  - Fees: $100 (no tax) = $100
  - Total = $1790
```

**TC3: Validation Warning**
```
Given: 
  - amount_duties = $1000 (generates $210 VAT)
  - amount_vat = $250 (declared, different)
When: Create tribute invoice
Then:
  - Invoice created
  - Warning message posted
  - Message: "VAT mismatch: Calculated $210 vs Declared $250"
```

**TC4: Zero Amounts**
```
Given: amount_income_tax = 0
When: Create tribute invoice
Then: IIGG tax still calculated if base amount exists
```

**TC5: Tax Configuration Change**
```
Given: IIGG tax changed from 6% to 7%
When: Create new invoice
Then: Percepciones calculated with 7%
```

---

## 🚀 DEPLOYMENT PLAN

### Phase 1: Preparation (Pre-deployment)
1. ✅ Backup database
2. ✅ Document current tax configuration
3. ✅ Identify existing invoices with tributes
4. ✅ Test in development environment

### Phase 2: Tax Infrastructure Setup
1. Create tax data file
2. Install/update module (taxes created)
3. Verify taxes appear in Accounting > Configuration > Taxes
4. Configure tax accounts if needed

### Phase 3: Product Update
1. Update product supplier_taxes_id
2. Remove obsolete product mappings
3. Update module
4. Verify products have correct taxes

### Phase 4: Code Deployment
1. Deploy updated Python code
2. Update module
3. Test invoice creation
4. Monitor logs for validation warnings

### Phase 5: User Training
1. Explain new validation fields
2. Show how to interpret tax mismatch warnings
3. Document when to adjust tax percentages

### Phase 6: Go-Live
1. Process test clearances
2. Validate all invoices
3. Monitor for issues
4. Provide support

---

## ⚠️ RISKS AND MITIGATION

### Risk 1: Tax Mismatch False Positives
**Cause:** Rounding differences between ARCA and Odoo  
**Mitigation:** Configurable tolerance threshold (default $1)  
**Fallback:** Option to disable validation

### Risk 2: Wrong Tax Percentages
**Cause:** Percepciones vary by company/product  
**Mitigation:** Make taxes configurable per company  
**Fallback:** Manual adjustment in invoice before validation

### Risk 3: Existing Invoices Break
**Cause:** Old invoices created with different structure  
**Mitigation:** This only affects NEW invoices  
**Fallback:** Keep old logic as fallback mode

### Risk 4: Argentina Localization Conflicts
**Cause:** l10n_ar may have similar taxes  
**Mitigation:** Check for existing taxes first, reuse if possible  
**Fallback:** Use our own taxes with unique names

---

## 📈 BENEFITS

### Immediate Benefits
- ✅ Automatic tax calculation (no manual mapping)
- ✅ Follows Odoo native patterns
- ✅ Less configuration required
- ✅ Validation ensures accuracy

### Long-term Benefits
- ✅ Easy to adjust tax percentages (legislation changes)
- ✅ Works with standard Odoo reports
- ✅ Compatible with Argentina localization
- ✅ Reduces user errors
- ✅ Maintainable architecture

### Business Benefits
- ✅ Faster invoice processing
- ✅ Reduced reconciliation errors
- ✅ Better compliance with ARCA requirements
- ✅ Audit trail maintained

---

## 📊 SUCCESS METRICS

- Invoice creation time reduced by 30%
- Tax validation warnings < 5% of invoices
- Zero manual corrections needed for standard cases
- User satisfaction increased (measured by support tickets)

---

## 🔄 ROLLBACK PLAN

If critical issues arise:

1. **Immediate:** Disable tax validation
2. **Short-term:** Revert to manual product mappings
3. **Data:** No data loss (only affects new invoices)
4. **Code:** Git revert to previous commit

---

## 📚 REFERENCE DOCUMENTATION

- Odoo Tax Groups: https://www.odoo.com/documentation/17.0/applications/finance/accounting/taxes.html
- Argentina Localization: l10n_ar module documentation
- Account Tax Model: odoo/addons/account/models/account_tax.py

---

## ✅ APPROVAL CHECKLIST

- [ ] Architecture reviewed
- [ ] Tax configuration verified
- [ ] Test cases defined
- [ ] Rollback plan approved
- [ ] User training material prepared
- [ ] Go/No-Go decision made

---

**Status:** READY FOR IMPLEMENTATION  
**Next Step:** Create tax data file and begin Task 1
