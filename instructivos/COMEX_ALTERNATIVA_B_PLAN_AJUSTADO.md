# Alternative B — Adjusted Implementation Plan with Edge Case Mitigations

## Date: February 27, 2026
## Status: Pre-Implementation Analysis

---

## 1. Production Data Analysis — Document Types per COMEX Operation Type

### 1.1 AFIP Document Types Relevant to COMEX

| Code | Prefix | Name | Internal Type | COMEX Usage |
|------|--------|------|---------------|-------------|
| 19 | FA-E | Export Invoices | invoice | Customer invoices for export operations |
| 20 | ND-E | Debit Notes for Foreign Operations | debit_note | Debit notes on export operations |
| 21 | NC-E | Credit Notes for Foreign Operations | credit_note | Customer refunds on exports |
| 66 | DI | Import Clearance (Despacho de Importación) | invoice | AFIP tributes for customs clearance |
| (none) | FA-I | Invoices and Receipts from Abroad | invoice | Foreign supplier invoices (no AFIP code) |
| (none) | NC-I | Foreign Credit Notes and Reimbursements | credit_note | Foreign supplier refunds (no AFIP code) |
| 1 | FA-A | Invoices A | invoice | Local Argentine service invoices |
| 99 | OC-X | Other Vouchers | invoice | Local costs (broker, freight, storage) |

### 1.2 Custom Journals in Production (No AFIP code)

| Journal ID | Code | Name | Type | Usage |
|------------|------|------|------|-------|
| 230 | DEXPO | Despacho de Exportación | sale | Export customs clearance costs (18 invoices) |
| 349 | PE | Permiso de Embarque | purchase | Export shipping permits, partner=AFIP (3 invoices) |

These journals have `l10n_latam_use_documents=False`, meaning no AFIP document type is applied.

### 1.3 Import Operations — Invoice Distribution (606 total invoices)

| Document Type | Count | Description |
|---------------|-------|-------------|
| **(66) Import Clearance** | **~506** | DI — AFIP tributes for Despacho de Importación |
| (99) Other Vouchers | 93 | Local costs: customs broker (despachante), freight, storage |
| (1) Invoices A | 7 | Local Argentine supplier invoices |

### 1.4 Export Operations — Invoice Distribution (51 total invoices)

| Document Type | Count | move_type | Description |
|---------------|-------|-----------|-------------|
| **(19) Export Invoices** | **26** | out_invoice | FA-E — Customer export invoices |
| No AFIP code (DEXPO) | 18 | out_invoice | Journal "Despacho de Exportación", partner=AFIP |
| No AFIP code (PE) | 3 | in_invoice | Journal "Permiso de Embarque", partner=AFIP |
| (21) Credit Notes Foreign Ops | 3 | out_refund | NC-E — Customer refunds |
| **(66) Import Clearance** | **1** | in_invoice | DI 25017EC01006613K — **ANOMALOUS** (see §1.5) |

### 1.5 The Anomalous Type 66 in Export Operation (Edge Case Already in Prod)

**Export Operation:** EXP/OSEYS/00244 (id=310), partner LA JICAREÑA SA

| Invoice | Doc Type | move_type | Amount | Journal |
|---------|----------|-----------|--------|---------|
| FA-E 00004-00000402 | (19) Export | out_invoice | $212,150 | Ventas AFIP PdV 4 |
| DEXPO/2025/00007 | (none) | out_invoice | $14,850.49 | Despacho de Exportación |
| DI 25017EC01006613K | **(66) Import Clearance** | in_invoice | $9,546.75 | Vendor Bills |

**Associated Customs Clearance:** DSP/2026/00307
- `vendor_bill_id` → DI 25017EC01006613K
- `dispatch_number` → 25017EC01006613K (note: "EC" = Exportación a Consumo)
- `vep_amount` → $9,546.75

**Analysis:** This is the **only** case in production where type 66 exists in an export operation.
The dispatch number format "25017**EC**01006613K" indicates this is an export clearance (not import).
It appears the operator used type 66 (the only AFIP customs code available) to register AFIP export tributes.

---

## 2. Semantic Analysis — Is Type 66 Valid for Export Operations?

### 2.1 According to AFIP/ARCA Official Documentation

In Argentina's tax authority (AFIP/ARCA) comprobante system:

- **Code 66 = "Despacho de Importación"** — Exclusively for IMPORT customs clearances
- For **exports**, the equivalent document is the **"Permiso de Embarque"** — This does **NOT have** an official AFIP comprobante code in the electronic billing system (RG 1415)
- AFIP's code 66 is specifically tied to the import clearance workflow and VEP payment system

### 2.2 What Should Be Used for Exports?

| Export Document | AFIP Code | How It Should Be Registered |
|-----------------|-----------|----------------------------|
| Factura de Exportación | **19** (FA-E) | Customer invoice with AFIP electronic authorization |
| Nota de Crédito Exportación | **21** (NC-E) | Credit note with AFIP electronic authorization |
| Permiso de Embarque (PE) | **None** | Custom journal without AFIP doc type |
| Export clearance tributes | **None** | Custom journal (DEXPO) or vendor bill without type 66 |

### 2.3 Production Reality vs. Semantic Correctness

| Approach | Count in Prod | Semantically Correct? | Notes |
|----------|---------------|----------------------|-------|
| DEXPO journal (no AFIP code) | 18 | ✅ Yes | Correct: separate journal for export clearance |
| PE journal (no AFIP code) | 3 | ✅ Yes | Correct: dedicated shipping permit journal |
| Type 66 for export | 1 | ❌ No | Workaround: using import code for export tributes |

### 2.4 Conclusion

**Type 66 is semantically incorrect for export operations.** The production case is a workaround, not a standard practice. The existing DEXPO and PE journals are the correct approach.

**Implication for Alternative B:** The autocreation logic should **only trigger for import operations** since type 66 is exclusively an import document. Export operations should use DEXPO/PE journals which don't need customs clearance autocreation.

---

## 3. Adjusted Alternative B — Implementation Plan with Edge Case Mitigations

### 3.1 Core Logic (Location: `_inverse_invoice_ids` in `comex_operation.py`)

```
When invoice_ids changes on a comex.operation:
  FOR EACH newly added invoice:
    IF invoice.l10n_latam_document_type_id.code == '66'
    AND operation.operation_type == 'import'
    AND invoice.move_type in ('in_invoice', 'in_receipt')
    AND invoice.state != 'cancel'
    AND NOT exists customs_clearance with same (operation_id, vendor_bill_id)
    THEN:
      Create comex.customs.clearance in draft
      Log message to chatter
```

### 3.2 Edge Case Matrix with Mitigations

#### EC-1: Only Import Operations

| Item | Detail |
|------|--------|
| **Edge Case** | Type 66 invoice added to export operation |
| **Risk** | Semantically incorrect clearance creation |
| **Mitigation** | Guard: `operation.operation_type == 'import'` |
| **Behavior** | Invoice is added to `invoice_ids` but no clearance is autocreated |
| **Chatter Msg** | None — export type 66 is an anomalous edge case, no automatic action |

#### EC-2: Only Vendor Bills (Not Refunds)

| Item | Detail |
|------|--------|
| **Edge Case** | Type 66 credit note (code 66, `in_refund`) added |
| **Risk** | Creating clearance for a refund has no business meaning |
| **Mitigation** | Guard: `move_type in ('in_invoice', 'in_receipt')` |
| **Behavior** | Refund is added to `invoice_ids`, no clearance created |
| **Chatter Msg** | None |

#### EC-3: Only Non-Cancelled Invoices

| Item | Detail |
|------|--------|
| **Edge Case** | Cancelled type 66 invoice in `invoice_ids` |
| **Risk** | Creating clearance for a void document |
| **Mitigation** | Guard: `invoice.state != 'cancel'` |
| **Behavior** | Cancelled invoices are filtered out by `_compute_invoice_ids` already |
| **Chatter Msg** | None |

#### EC-4: Idempotency — No Duplicate Clearances

| Item | Detail |
|------|--------|
| **Edge Case** | Same type 66 invoice re-added (recomputation or manual re-add) |
| **Risk** | Creating duplicate `comex.customs.clearance` for same vendor bill |
| **Mitigation** | Check: `self.env['comex.customs.clearance'].search([('operation_id', '=', op.id), ('vendor_bill_id', '=', inv.id)])` |
| **Behavior** | If clearance already exists → skip (no-op) |
| **Chatter Msg** | None |

#### EC-5: Cross-Operation Duplicate Detection

| Item | Detail |
|------|--------|
| **Edge Case** | Type 66 invoice already linked to a clearance in ANOTHER operation |
| **Risk** | One vendor bill linked to multiple clearances across operations |
| **Mitigation** | Check: `self.env['comex.customs.clearance'].search([('vendor_bill_id', '=', inv.id)])` |
| **Behavior** | If clearance exists in another operation → skip autocreation, log warning |
| **Chatter Msg** | ⚠️ "Invoice {name} already linked to clearance {clearance.name} in operation {op.name}. No clearance created." |

#### EC-6: Historical Data — Existing Orphan Type 66 Invoices

| Item | Detail |
|------|--------|
| **Edge Case** | Existing type 66 invoices in operations without clearances |
| **Risk** | Autocreation only triggers on write, not on existing data |
| **Mitigation** | Separate one-time data remediation script (see §4) |
| **Behavior** | Script creates missing clearances for historical orphaned type 66 |
| **Timeline** | Execute BEFORE deploying the code change |

#### EC-7: Batch Write — Multiple Type 66 Invoices at Once

| Item | Detail |
|------|--------|
| **Edge Case** | Multiple type 66 invoices added simultaneously to `invoice_ids` |
| **Risk** | Performance or transaction issues with multiple clearance creations |
| **Mitigation** | Use `create_multi` pattern: collect all vals, create in single batch |
| **Behavior** | All clearances created atomically in one `create()` call |
| **Chatter Msg** | One message per created clearance |

#### EC-8: RPC/API Writes

| Item | Detail |
|------|--------|
| **Edge Case** | `invoice_ids` modified via XML-RPC, import, or API |
| **Risk** | Autocreation logic bypassed if only `_compute_invoice_ids` triggers |
| **Mitigation** | Logic lives in `_inverse_invoice_ids` which triggers on ANY write to `invoice_ids` (UI, API, or import) |
| **Behavior** | Same autocreation happens regardless of write source |
| **Chatter Msg** | Same as interactive |

#### EC-9: Draft vs Posted Invoice

| Item | Detail |
|------|--------|
| **Edge Case** | Type 66 in draft state added to operation |
| **Risk** | Clearance created for an unconfirmed invoice |
| **Mitigation** | **No guard needed** — draft invoices are intentionally valid |
| **Rationale** | Clearance is also created in `draft` state. When invoice is posted, data syncs via `_compute_tribute_amounts`. Creating early allows users to fill in other clearance fields. |
| **Behavior** | Clearance created in draft. `vendor_bill_id` linked. Auto-fill runs on vendor bill confirmation. |

#### EC-10: Clearance Required Fields

| Item | Detail |
|------|--------|
| **Edge Case** | Autocreation must provide all required fields |
| **Risk** | `ValidationError` on clearance create |
| **Required fields** | `operation_id` (from context), `name` (auto-sequence), `company_id` (related), `clearance_type` (default='definitive') |
| **Mitigation** | Provide minimal vals: `{'operation_id': op.id, 'vendor_bill_id': inv.id}` — all other required fields have defaults or are related |
| **Behavior** | Clearance created successfully with: name=DSP/YYYY/NNNNN, state=draft, clearance_type=definitive |

#### EC-11: Compute Reentrancy — Infinite Loop

| Item | Detail |
|------|--------|
| **Edge Case** | Creating clearance triggers `_compute_invoice_ids` reentrantly |
| **Risk** | `_compute_invoice_ids` depends on `customs_clearance_ids.vendor_bill_id`. Creating a clearance with `vendor_bill_id` would retrigger the compute. |
| **Mitigation** | Context flag: `self.with_context(skip_clearance_autocreation=True)` during clearance creation |
| **Behavior** | Compute retriggers normally (adding clearance vendor bill to `invoice_ids`), but the inverse skip check prevents re-entering autocreation |

#### EC-12: Vendor Bill ID Field Auto-Fill

| Item | Detail |
|------|--------|
| **Edge Case** | Autocreated clearance should auto-fill fields from vendor bill |
| **Risk** | `_onchange_vendor_bill_id_auto_fill` is an onchange, doesn't fire on programmatic `create()` |
| **Mitigation** | After `create()`, explicitly call the auto-fill logic: set `dispatch_number` and `vep_amount` from the invoice in `vals` |
| **Behavior** | Clearance created with `dispatch_number` and `vep_amount` already populated |

#### EC-13: UI Domain — Prevent Type 66 in Export Operations (Vista)

| Item | Detail |
|------|--------|
| **Edge Case** | User manually adds a type 66 invoice to an export operation via UI |
| **Risk** | Semantically incorrect — type 66 (Despacho de Importación) does not apply to exports |
| **Mitigation** | Domain filters on 3 views that prevent type 66 selection in export context |
| **Behavior** | Type 66 invoices hidden from selection dialogs when operation is export |
| **Reverse side** | From invoice form, if invoice IS type 66, only import operations are offered |

**Views Modified:**

| # | File | Field | Domain Logic |
|---|------|-------|-------------|
| 1 | `comex_operation_views.xml` — **Tree** | `invoice_ids` | `'|', (doc_type = False), (doc_type.code != '66' IF export ELSE '__noop__')` |
| 2 | `comex_operation_views.xml` — **Form tab** | `invoice_ids` | Same domain as tree |
| 3 | `account_move_views.xml` — **Invoice form** | `comex_operation_ids` | `operation_type IN ['import'] IF is_type_66 ELSE ['import','export']` |

**Domain evaluation logic:**

- **Export operation → `invoice_ids`**: Shows all invoices EXCEPT those with `l10n_latam_document_type_id.code == '66'`. Invoices without document type (DEXPO, PE journals) pass through.
- **Import operation → `invoice_ids`**: Shows ALL invoices including type 66 (the `'__noop__'` value never matches any real code, so `!= '__noop__'` is always True).
- **Type 66 invoice → `comex_operation_ids`**: Only import operations offered for linking.
- **Non-66 invoice → `comex_operation_ids`**: Both import and export operations available.

**Why `'__noop__'`?**: Odoo 17 OWL domain parser supports Python ternary in value position. When `operation_type == 'import'`, the condition evaluates to `('code', '!=', '__noop__')` which is always True (no document has code `__noop__`), effectively disabling the filter.

---

## 4. Data Remediation Plan (Pre-Deployment)

### 4.1 Diagnostic: Find Orphan Type 66 Invoices

```python
# Pseudocode for diagnostics script
import_ops = env['comex.operation'].search([('operation_type', '=', 'import')])
for op in import_ops:
    type_66_invoices = op.invoice_ids.filtered(
        lambda inv: inv.l10n_latam_document_type_id.code == '66'
    )
    for inv in type_66_invoices:
        has_clearance = env['comex.customs.clearance'].search([
            ('operation_id', '=', op.id),
            ('vendor_bill_id', '=', inv.id),
        ], limit=1)
        if not has_clearance:
            print(f"ORPHAN: Op {op.name} | Invoice {inv.name}")
```

### 4.2 Remediation: Create Missing Clearances

Execute as server action or script BEFORE deploying the code:

```python
# For each orphan found, create clearance with minimal data
clearance = env['comex.customs.clearance'].create({
    'operation_id': op.id,
    'vendor_bill_id': inv.id,
    'dispatch_number': inv.l10n_latam_document_number,
    'vep_amount': inv.amount_total,
})
```

### 4.3 Export Operation Type 66 Anomaly

The single case of DI 25017EC01006613K in EXP/OSEYS/00244:
- **Decision:** Leave as-is — it has a clearance (DSP/2026/00307) already linked
- **No action needed** — the autocreation logic won't affect it since it guards by `operation_type == 'import'`
- **Future consideration:** If users need to register export tributes with type 66, a separate workflow should be designed

---

## 5. Implementation Pseudocode

### 5.1 Modified `_inverse_invoice_ids` in `comex_operation.py`

```python
def _inverse_invoice_ids(self):
    """Allow manual editing of invoice_ids field.
    
    Automatically creates customs clearances for newly added
    type 66 invoices in import operations.
    """
    if self.env.context.get('skip_clearance_autocreation'):
        return
    
    Clearance = self.env['comex.customs.clearance']
    clearances_to_create = []
    
    for operation in self:
        # EC-1: Only import operations
        if operation.operation_type != 'import':
            continue
        
        # Find type 66 invoices in current invoice_ids
        type_66_invoices = operation.invoice_ids.filtered(
            lambda inv: (
                inv.l10n_latam_document_type_id and
                inv.l10n_latam_document_type_id.code == '66' and
                inv.move_type in ('in_invoice', 'in_receipt') and  # EC-2
                inv.state != 'cancel'  # EC-3
            )
        )
        
        for inv in type_66_invoices:
            # EC-4: Check idempotency (same operation)
            existing = Clearance.search([
                ('operation_id', '=', operation.id),
                ('vendor_bill_id', '=', inv.id),
            ], limit=1)
            if existing:
                continue
            
            # EC-5: Check cross-operation duplicate
            cross_op = Clearance.search([
                ('vendor_bill_id', '=', inv.id),
                ('operation_id', '!=', operation.id),
            ], limit=1)
            if cross_op:
                operation.message_post(
                    body=_(
                        "Invoice %(invoice)s is already linked to clearance "
                        "%(clearance)s in operation %(operation)s. "
                        "No clearance created automatically.",
                        invoice=inv.name,
                        clearance=cross_op.name,
                        operation=cross_op.operation_id.name,
                    )
                )
                continue
            
            # EC-10 + EC-12: Prepare vals with required fields + auto-fill
            vals = {
                'operation_id': operation.id,
                'vendor_bill_id': inv.id,
            }
            if hasattr(inv, 'l10n_latam_document_number') and inv.l10n_latam_document_number:
                vals['dispatch_number'] = inv.l10n_latam_document_number
            if inv.amount_total:
                vals['vep_amount'] = inv.amount_total
            
            clearances_to_create.append((operation, inv, vals))
    
    # EC-7: Batch create all clearances
    if clearances_to_create:
        vals_list = [item[2] for item in clearances_to_create]
        # EC-11: Skip reentrancy
        new_clearances = Clearance.with_context(
            skip_clearance_autocreation=True
        ).create(vals_list)
        
        # Post chatter messages
        for (operation, inv, _vals), clearance in zip(clearances_to_create, new_clearances):
            operation.message_post(
                body=_(
                    "Customs clearance %(clearance)s automatically created "
                    "from invoice %(invoice)s (Document Type 66).",
                    clearance=clearance.name,
                    invoice=inv.name,
                )
            )
```

---

## 6. What Will NOT Change

1. **Non-66 invoices** — No effect on commercial invoices, local costs, or refunds
2. **Existing clearance creation workflow** — Manual creation still works as before
3. **`_compute_invoice_ids`** — No changes to the compute logic
4. **`vendor_bill_id` domain** on clearance form — Still defaults to type 66
5. **DEXPO / PE journals** — No changes to export customs document handling

## 6.1 What WILL Change (Summary)

| Change | File | Purpose |
|--------|------|---------|
| `_inverse_invoice_ids` enhanced | `comex_operation.py` | Autocreate clearances for type 66 in imports |
| Domain on `invoice_ids` (tree) | `comex_operation_views.xml` | Block type 66 selection in export ops |
| Domain on `invoice_ids` (form tab) | `comex_operation_views.xml` | Block type 66 selection in export ops |
| Domain on `comex_operation_ids` | `account_move_views.xml` | Type 66 invoices only link to import ops |

---

## 7. Test Matrix

| # | Scenario | Expected Result |
|---|----------|-----------------|
| T1 | Add type 66 to import op (no clearance exists) | Clearance auto-created in draft |
| T2 | Add type 66 to import op (clearance already exists) | No duplicate, no-op (EC-4) |
| T3 | Add type 66 to export op | No clearance created (EC-1) |
| T4 | Add type 66 refund to import op | No clearance created (EC-2) |
| T5 | Add non-66 invoice to import op | No clearance created |
| T6 | Add type 66 already linked to another op's clearance | Warning in chatter (EC-5) |
| T7 | Add 3 type 66 invoices at once | 3 clearances created in batch (EC-7) |
| T8 | Remove type 66 from import op | Clearance remains (not deleted) |
| T9 | Recompute triggers `_inverse_invoice_ids` | No duplicates (idempotency EC-4) |
| T10 | Auto-fill: clearance has dispatch_number and vep_amount | Fields populated from invoice (EC-12) |
| T11 | XML-RPC write to `invoice_ids` with type 66 | Same autocreation (EC-8) |
| T12 | Export op: open invoice selector | Type 66 invoices NOT shown (EC-13 domain) |
| T13 | Import op: open invoice selector | Type 66 invoices shown normally |
| T14 | Type 66 invoice form: open operation selector | Only import operations shown (EC-13 domain) |
| T15 | Non-66 invoice form: open operation selector | Both import and export operations shown |

---

## 8. Deployment Sequence

1. **Run diagnostic script** — Identify orphan type 66 in import operations
2. **Run remediation script** — Create missing clearances for historical data
3. **Deploy code changes:**
   - `comex_operation.py` — Updated `_inverse_invoice_ids` with autocreation
   - `comex_operation_views.xml` — Domain filter on `invoice_ids` (tree + form)
   - `account_move_views.xml` — Domain filter on `comex_operation_ids`
4. **Verify domains** — Open export op form, confirm type 66 not selectable
5. **Verify autocreation** — Add type 66 to test import op, confirm clearance created
6. **Monitor** — Check chatter logs for autocreation messages in first 2 weeks

---

## 9. Production Anomaly: EXP/OSEYS/00244

The existing type 66 (DI 25017EC01006613K) in export operation 310:
- **Status:** Already has clearance DSP/2026/00307 linked → no orphan
- **Domain impact:** The new domain won't retroactively remove it from `invoice_ids` (domains only affect selection dialogs, not stored data)
- **Decision:** Leave as-is. The clearance already exists and functions correctly.
- **Future:** If more export tributes need type 66, design a dedicated workflow (export clearance type)
