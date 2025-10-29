# Econovo - Draft MTO/MO Control

## Overview

This module provides **granular control** over when Manufacturing Orders (MO) should stay in **Draft state** vs. **auto-confirm**, based on the source type (MTO, MTS, MPS, Orderpoint).

Unlike the original `draft_mto_mo` module which affects ALL manufacturing orders unconditionally, this enhanced version allows you to configure the behavior at three different levels with full flexibility.

---

## Features

### 🎯 Multi-Level Configuration Hierarchy

The module implements a **3-level hierarchy** where each level can override the previous:

```
1. GLOBAL (System Settings)
   ↓ Can be overridden by
2. PRODUCT (Product Template)
   ↓ Can be overridden by
3. USER (User Preferences)
```

### 📋 Source Types Supported

Configure independently for each manufacturing source:

| Source Type | Description | Example |
|-------------|-------------|---------|
| **MTO** | Make To Order from Sales | Customer orders a product → SO creates MO |
| **MTS** | Make To Stock replenishment | Stock below minimum → System creates MO |
| **MPS** | Master Production Schedule | Planned production from MPS module |
| **Orderpoint** | Reordering Rules | Min/Max rules trigger MO creation |

### ✅ Maintains Odoo Native Behavior

Unlike simple overrides, this module **preserves all Odoo standard features**:

- ✅ **MO Consolidation**: Non-MTO orders still consolidate quantities
- ✅ **Quantity Validation**: Prevents negative quantity MOs
- ✅ **Traceability**: Maintains message posting in chatter
- ✅ **Native Filters**: Respects `_should_auto_confirm_procurement_mo`

---

## Configuration

### Level 1: Global Settings

**Location:** Settings → General Settings → Manufacturing Order Draft Control

**Options:**
- **Native Odoo Behavior**: Use Odoo's standard logic (no changes)
- **All MOs stay in Draft**: Never auto-confirm any MO
- **Custom by Source Type**: Configure individually for MTO/MTS/MPS/Orderpoint

**Example:**
```
Global Policy: Custom by Source Type
  ☑ MTO: Keep Draft
  ☐ MTS: Native Flow (auto-confirm)
  ☐ MPS: Native Flow
  ☐ Orderpoint: Native Flow
```

**Result:** All MOs from sales orders stay in draft, everything else auto-confirms.

---

### Level 2: Product Override

**Location:** Product → Manufacturing tab → MO Draft Control

**Options:**
- **Use Global Settings**: Follow system configuration
- **Native Odoo Behavior**: Ignore global, use Odoo standard
- **Always Keep Draft**: This product always stays draft
- **Always Auto-Confirm**: This product always auto-confirms
- **Custom by Source Type**: Configure per source for this product

**Example:**
```
Product: [Critical Component X]
Policy: Always Keep Draft
```

**Result:** All MOs for this product stay in draft, regardless of global settings or source type.

---

### Level 3: User Override

**Location:** User → Preferences tab → Manufacturing Order Preferences

**Options:**
- **Use Global/Product Settings**: Follow configured rules
- **Native Odoo Behavior**: Ignore all settings, use Odoo standard
- **Always Keep Draft**: All MOs I create stay draft
- **Always Auto-Confirm**: All MOs I create auto-confirm
- **Custom by Source Type**: Configure per source for me

**Example:**
```
User: [Junior Planner]
Policy: Always Keep Draft
```

**Result:** All MOs created by this user stay in draft, requiring supervisor review.

**⚠️ Important - User Detection:**

The module identifies the responsible user with the following priority:

1. **Session User** (highest priority): The user who clicked "Confirm" on the Sales Order
2. **Sales Order User**: The salesperson assigned to the SO (if MTO)
3. **Current User** (fallback): The user executing the action (may be OdooBot for automated processes)

This ensures that user-level policies apply to the **actual person** initiating the action, not the system user running background processes.

**Example:**
```
Mitchell Admin configures: Custom (MTO=Draft)
Mitchell Admin clicks "Confirm" on SO
→ The module uses Mitchell Admin's policy, not OdooBot
→ MO stays in DRAFT as configured
```

---

## Use Cases

### Case 1: Conservative Company

**Requirement:** Review all sales-related production, auto-confirm replenishment

**Configuration:**
```
GLOBAL: Custom
  ☑ MTO: Keep Draft
  ☐ MTS: Native Flow
  ☐ MPS: Native Flow
  ☐ Orderpoint: Native Flow
```

**Benefit:** Sales-driven production requires manual review, internal replenishment is automated.

---

### Case 2: Critical Product Exception

**Requirement:** One product always needs review, others follow global rules

**Configuration:**
```
GLOBAL: Native Odoo Behavior (auto-confirm everything)

PRODUCT [Regulated Component]: Always Keep Draft
```

**Benefit:** 99% of products auto-confirm, but the regulated component always requires approval.

---

### Case 3: Junior User Restriction

**Requirement:** Junior planners must have supervisor review, seniors can auto-confirm

**Configuration:**
```
GLOBAL: Custom
  ☐ MTO: Native Flow
  ☐ MTS: Native Flow
  ☐ MPS: Native Flow
  ☐ Orderpoint: Native Flow

USER [Junior Planner]: Always Keep Draft
USER [Senior Planner]: Use Global Settings (auto-confirm)
```

**Benefit:** Experience-based workflow control without changing product or global settings.

---

### Case 4: Mixed Workflow

**Requirement:** 
- MTO from sales → Always draft
- High-value products → Always draft
- Normal replenishment → Auto-confirm
- Junior users → Everything draft

**Configuration:**
```
GLOBAL: Custom
  ☑ MTO: Keep Draft
  ☐ MTS: Native Flow
  ☐ MPS: Native Flow
  ☐ Orderpoint: Native Flow

PRODUCT [Expensive Machine]: Always Keep Draft

USER [Junior]: Always Keep Draft
USER [Senior]: Use Global Settings
```

**Benefit:** Maximum flexibility with clear precedence rules.

---

## Technical Details

### User Detection & Propagation

The module implements sophisticated user tracking to ensure user-level policies apply correctly:

**Problem Solved:**
When confirming a Sales Order, Odoo switches execution context to system users (OdooBot) for background processes. This would cause user policies to be ignored.

**Solution:**
1. **Capture**: `sale.order.action_confirm()` captures the original user ID (session user)
2. **Propagate**: User ID is passed through context as `original_user_id`
3. **Retrieve**: `stock.rule._get_responsible_user()` retrieves with priority:
   - Original user from context (the one who clicked "Confirm")
   - Sales order user (salesperson assigned to SO)
   - Current executing user (fallback)

**Code Flow:**
```python
# In sale.order.action_confirm()
current_user_id = self.env.uid  # Capture session user
return super().with_context(
    original_user_id=current_user_id  # Propagate through context
).action_confirm()

# In stock.rule._get_responsible_user()
original_user_id = self.env.context.get('original_user_id')
if original_user_id:
    return self.env['res.users'].browse(original_user_id)
# Fallback to SO user or current user
```

**Result:**
- ✅ User policies apply to the person who initiated the action
- ✅ Works correctly even with automated/background processes
- ✅ Proper attribution for audit trails

---

### Detection Logic

The module reliably detects source types using Odoo's native fields:

```python
# MTO Detection (robust, sequence-independent)
if procurement.values.get('sale_line_id'):
    # Direct: SO line linked
    source_type = 'mto'
elif group.sale_id:
    # Via procurement group: SO relationship
    source_type = 'mto'
elif rule.route_id == mto_route:
    # Via route configuration
    source_type = 'mto'

# MPS Detection
elif procurement.origin == 'MPS':
    source_type = 'mps'

# Orderpoint Detection
elif procurement.values.get('orderpoint_id'):
    source_type = 'orderpoint'

# MTS (Default)
else:
    source_type = 'mts'
```

**MTO Detection Priority:**
1. `sale_line_id` in procurement values (most direct)
2. Procurement group linked to sales order (reliable for nested MOs)
3. Route configured as MTO (fallback)

This multi-level detection ensures MTO is correctly identified even when:
- Sales order sequences don't start with "S"
- Multiple levels of nested manufacturing orders
- Custom route configurations

### Decision Flow

```
1. Detect source type (MTO/MTS/MPS/Orderpoint)
2. Identify responsible user:
   a. Original user from context (session user who clicked button)
   b. Sales order user (if MTO)
   c. Current user (fallback)
3. Get GLOBAL decision for this source type
4. IF product has override:
     Use PRODUCT decision
5. IF user has override:
     Use USER decision (from identified user, not OdooBot)
6. Apply decision (draft or confirm)
```

### Performance

- **Minimal overhead**: Only 3 lookups per MO (global, product, user)
- **Cached parameters**: System parameters are cached by Odoo
- **No extra queries**: Uses existing procurement data

---

## Installation

1. Copy module to `addons` directory
2. Update Apps List
3. Install "Econovo - Draft MTO/MO Control"

**Dependencies:**
- `mrp` (Manufacturing)
- `stock` (Inventory)
- `sale_stock` (Sales & Inventory)

---

## Upgrade from `draft_mto_mo`

If you have the original `draft_mto_mo` module installed:

1. **Before upgrade:** Note your current behavior (all MOs stay draft)
2. **Install this module:** Uninstall old, install new
3. **Configure:** Set global policy to match previous behavior:
   - Old behavior = New policy: "All MOs stay in Draft"
4. **Refine:** Gradually add exceptions at product/user level

**Migration equivalent:**
```
Old Module: Everything stays draft
↓
New Module: Global Policy = "All MOs stay in Draft"
```

---

## Support

**Author:** Jose D. Leonett  
**Website:** https://github.com/josedleonett  
**License:** AGPL-3  
**Version:** 17.0.1.0.0

---

## Changelog

### Version 17.0.1.0.0 (2025-10-29)
- Initial release
- Multi-level configuration hierarchy (Global → Product → User)
- Support for 4 source types (MTO, MTS, MPS, Orderpoint)
- **User session propagation**: Captures actual user who confirms SO, not system user
- **Robust MTO detection**: Multi-level detection via sale_line_id, group.sale_id, and route
- **Windows compatibility**: ASCII logging for cp1252 encoding
- Maintains all Odoo native behavior (consolidation, validation, traceability)
- Comprehensive UI with help texts and visibility rules
- Detailed debug logging for troubleshooting

### Key Technical Improvements:
- ✅ User context propagation through `sale.order.action_confirm()`
- ✅ Priority-based user detection (session → SO → current)
- ✅ Sequence-independent MTO detection via procurement group relationships
- ✅ Fixed recordset handling for group_id (no unnecessary browse() calls)
- ✅ Unicode-safe logging for Windows terminals
