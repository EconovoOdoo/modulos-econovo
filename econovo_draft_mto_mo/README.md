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

### Detection Logic

The module reliably detects source types using Odoo's native fields:

```python
# MTO Detection
if rule.route_id == mto_route or procurement.values.get('sale_line_id'):
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

### Decision Flow

```
1. Detect source type (MTO/MTS/MPS/Orderpoint)
2. Get GLOBAL decision for this source type
3. IF product has override:
     Use PRODUCT decision
4. IF user has override:
     Use USER decision
5. Apply decision (draft or confirm)
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
- Maintains all Odoo native behavior (consolidation, validation, traceability)
- Comprehensive UI with help texts and visibility rules
