# Manufacturing Order Draft Decision Matrix

## Configuration Hierarchy

The module uses a **3-level hierarchy** where each level can override the previous:

```
Global (Settings) → Product → User
```

## Decision Policies

Each level can be configured with one of these policies:

| Policy | Description |
|--------|-------------|
| **use_global** / **use_parent** | Use the previous level's configuration |
| **native_flow** | Always follow Odoo's native behavior (auto-confirm all MOs) |
| **always_draft** | Always keep MOs in draft state |
| **always_confirm** | Always auto-confirm MOs (override draft settings) |
| **custom** | Configure separately for each source type (MTO/MTS/MPS/Orderpoint) |

---

## Complete Decision Matrix

This matrix shows the **FINAL BEHAVIOR** based on all three levels of configuration.

### Legend:
- ✅ **DRAFT** = MO stays in draft state
- ❌ **CONFIRM** = MO is auto-confirmed
- 🔵 **Policy takes precedence** = Higher level policy overrides lower level

---

## Scenario Matrix

### When **GLOBAL = custom (MTO=Draft)**:

| Product Policy | User Policy | Result for MTO | Result for MTS/MPS/Orderpoint | Explanation |
|----------------|-------------|----------------|-------------------------------|-------------|
| **use_global** | **use_global** | ✅ DRAFT | ❌ CONFIRM | Uses global custom settings |
| **use_global** | **native_flow** | ❌ CONFIRM | ❌ CONFIRM | 🔵 User forces native (all confirm) |
| **use_global** | **always_draft** | ✅ DRAFT | ✅ DRAFT | 🔵 User forces all draft |
| **use_global** | **always_confirm** | ❌ CONFIRM | ❌ CONFIRM | 🔵 User forces all confirm |
| **use_global** | **custom (MTO=False)** | ❌ CONFIRM | (depends on user) | 🔵 User overrides MTO to confirm |
| **native_flow** | **use_global** | ❌ CONFIRM | ❌ CONFIRM | 🔵 Product forces native flow |
| **native_flow** | **always_draft** | ✅ DRAFT | ✅ DRAFT | 🔵 User has final say (draft) |
| **always_draft** | **use_global** | ✅ DRAFT | ✅ DRAFT | 🔵 Product forces all draft |
| **always_draft** | **native_flow** | ❌ CONFIRM | ❌ CONFIRM | 🔵 User has final say (native) |
| **always_confirm** | **use_global** | ❌ CONFIRM | ❌ CONFIRM | 🔵 Product forces all confirm |
| **always_confirm** | **always_draft** | ✅ DRAFT | ✅ DRAFT | 🔵 User has final say (draft) |
| **custom (MTO=False)** | **use_global** | ❌ CONFIRM | (depends on product) | Product overrides MTO to confirm |
| **custom (MTO=False)** | **custom (MTO=True)** | ✅ DRAFT | (depends on user) | 🔵 User has final say |

---

## Hierarchy Rules (Blood Type Analogy)

Think of it like blood type compatibility:

### 🩸 "Donor" → "Recipient" Flow:

```
Global Settings (Universal Donor)
    ↓ (can be overridden by)
Product Settings (Specific Type)
    ↓ (can be overridden by)
User Settings (Most Specific - Final Decision)
```

### Priority Rules:

1. **User** always has the **final say** (like O- is universal donor, but AB+ is universal recipient)
2. **Product** can override **Global** (but not User)
3. **Global** is the **default/fallback** (when others use "use_global/use_parent")

---

## Decision Truth Table (for MTO source type)

### When ALL levels are "custom":

| Global MTO | Product MTO | User MTO | Final Result | Why? |
|------------|-------------|----------|--------------|------|
| ✅ True (Draft) | ✅ True (Draft) | ✅ True (Draft) | ✅ DRAFT | All agree: keep draft |
| ✅ True (Draft) | ✅ True (Draft) | ❌ False (Confirm) | ❌ CONFIRM | 🔵 User overrides |
| ✅ True (Draft) | ❌ False (Confirm) | ✅ True (Draft) | ✅ DRAFT | 🔵 User overrides product |
| ✅ True (Draft) | ❌ False (Confirm) | ❌ False (Confirm) | ❌ CONFIRM | 🔵 User confirms product override |
| ❌ False (Confirm) | ✅ True (Draft) | ✅ True (Draft) | ✅ DRAFT | 🔵 User overrides all |
| ❌ False (Confirm) | ✅ True (Draft) | ❌ False (Confirm) | ❌ CONFIRM | 🔵 User overrides product |
| ❌ False (Confirm) | ❌ False (Confirm) | ✅ True (Draft) | ✅ DRAFT | 🔵 User overrides |
| ❌ False (Confirm) | ❌ False (Confirm) | ❌ False (Confirm) | ❌ CONFIRM | All agree: confirm |

---

## Quick Reference: Common Scenarios

### Scenario 1: "Only MTO from sales should stay draft"
```
Global:  custom (MTO=✅, MTS=❌, MPS=❌, Orderpoint=❌)
Product: use_global
User:    use_global
Result:  Sales orders → DRAFT, Everything else → CONFIRM
```

### Scenario 2: "Product X always stays draft, everything else normal"
```
Global:  native_flow (all auto-confirm)
Product X: always_draft
User:    use_global
Result:  Product X → DRAFT, All other products → CONFIRM
```

### Scenario 3: "User Alice reviews all MOs manually"
```
Global:  native_flow (all auto-confirm)
Product: use_global
Alice:   always_draft
Result:  For Alice → ALL DRAFT, For other users → CONFIRM
```

### Scenario 4: "Careful with Product Y, but User Bob is expert"
```
Global:  native_flow
Product Y: always_draft
Bob:     always_confirm (only for Product Y)
Result:  
  - Alice creates Y → DRAFT (product policy)
  - Bob creates Y → CONFIRM (user overrides product)
  - Anyone creates Z → CONFIRM (global native)
```

---

## Configuration Flow Chart

```
START: MO needs to be created
    ↓
┌───────────────────────────────────────┐
│ 1. Detect Source Type                 │
│    - MTO (from sales?)                │
│    - MTS (replenishment?)             │
│    - MPS (master schedule?)           │
│    - Orderpoint (reorder rules?)      │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 2. Check GLOBAL Settings              │
│    - Policy: native/draft/confirm/custom │
│    - If custom: check boolean for source type │
│    → Decision: DRAFT or CONFIRM       │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 3. Check PRODUCT Settings             │
│    - Policy != use_global?            │
│      YES → Override previous decision │
│      NO → Keep previous decision      │
└───────────────┬───────────────────────┘
                ↓
┌───────────────────────────────────────┐
│ 4. Check USER Settings                │
│    - Policy != use_global?            │
│      YES → Override (FINAL DECISION)  │
│      NO → Keep previous decision      │
└───────────────┬───────────────────────┘
                ↓
        ╔═══════════════╗
        ║ FINAL RESULT: ║
        ║ DRAFT or      ║
        ║ AUTO-CONFIRM  ║
        ╚═══════════════╝
```

---

## Policy Override Matrix (Simplified)

| Current Level | Policy Set | Overrides Previous? | Behavior |
|---------------|------------|---------------------|----------|
| Global | any | N/A | Sets baseline for all |
| Product | **use_global** | ❌ NO | Uses global decision |
| Product | **native/draft/confirm/custom** | ✅ YES | Overrides global |
| User | **use_global** | ❌ NO | Uses product/global decision |
| User | **native/draft/confirm/custom** | ✅ YES | Overrides everything (final) |

---

## Examples with Your Current Setup

You mentioned you have set **Custom** with **MTO=Draft** at all 3 levels. Let's trace the decision:

### Example: Confirming a Sales Order (MTO source)

```
┌─ DETECTION ─────────────────────────────────────┐
│ Source: sale.order.action_confirm()             │
│ Has sale_line_id? YES                            │
│ → Detected as: MTO                               │
└──────────────────────────────────────────────────┘

┌─ LEVEL 1: GLOBAL ───────────────────────────────┐
│ Policy: custom                                   │
│ MTO checkbox: ✅ TRUE (keep draft)               │
│ → Decision: DRAFT                                │
└──────────────────────────────────────────────────┘

┌─ LEVEL 2: PRODUCT ──────────────────────────────┐
│ Policy: custom (not use_global)                  │
│ MTO checkbox: ✅ TRUE (keep draft)               │
│ → Overrides global: DRAFT                        │
└──────────────────────────────────────────────────┘

┌─ LEVEL 3: USER ─────────────────────────────────┐
│ Policy: custom (not use_global)                  │
│ MTO checkbox: ✅ TRUE (keep draft)               │
│ → FINAL DECISION: DRAFT                          │
└──────────────────────────────────────────────────┘

╔══════════════════════════════════════════════════╗
║ EXPECTED RESULT: MO should stay in DRAFT state  ║
╚══════════════════════════════════════════════════╝
```

**If MOs are NOT staying in draft, possible causes:**

1. ❌ Module not fully loaded/restarted
2. ❌ Configuration not saved correctly
3. ❌ Source type detection failing (detecting as MTS instead of MTO)
4. ❌ Another module overriding `_run_manufacture` with higher priority

---

## Debugging Steps

Run these commands in Odoo shell to verify configuration:

```python
# Check global settings
params = env['ir.config_parameter'].sudo()
print("Global Policy:", params.get_param('econovo_draft_mto_mo.global_policy'))
print("Draft for MTO:", params.get_param('econovo_draft_mto_mo.draft_for_mto'))

# Check product settings
product = env['product.template'].search([('name', '=', 'Your Product Name')], limit=1)
print("Product Policy:", product.mo_draft_policy)
print("Product MTO:", product.mo_draft_mto)

# Check user settings
user = env.user
print("User Policy:", user.mo_draft_policy)
print("User MTO:", user.mo_draft_mto)
```

---

## Summary

The module provides **maximum flexibility** through a clear hierarchy:

- **3 Levels**: Global → Product → User
- **5 Policies per level**: use_global, native_flow, always_draft, always_confirm, custom
- **4 Source Types**: MTO, MTS, MPS, Orderpoint
- **Final Decision**: User always has the last word

Think of it as: **The more specific the level, the higher the priority.**
