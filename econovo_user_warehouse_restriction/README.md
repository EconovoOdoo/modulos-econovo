# Econovo - User Warehouse Restriction Extension

## Overview

This module **extends** the `user_warehouse_restriction` module (by Cybrosys Technologies) to provide comprehensive warehouse access control with flexible restriction levels and transit warehouse support for inter-warehouse collaboration.

**IMPORTANT**: This is an **extension module**, not a standalone solution. It requires the base module `user_warehouse_restriction` to function properly.

## Version

- **Module Version**: 17.0.1.0.1
- **Odoo Version**: 17.0
- **Author**: Jose D. Leonett
- **License**: AGPL-3
- **Depends**: `user_warehouse_restriction` (Cybrosys Technologies)

## Architecture

### Module Inheritance

This module inherits from and extends `user_warehouse_restriction`:

```
user_warehouse_restriction (Base - Cybrosys)
    │
    ├─ Provides: Base group, warehouse.user_ids field
    ├─ Restricts: stock.picking.type, stock.location, stock.warehouse, stock.picking
    │
    └─► econovo_user_warehouse_restriction (Extension)
         │
         ├─ Group: Source Only (inherits Base group)
         │   ├─ Adds: Record Rules for quant, move, move.line
         │   └─ Validates: Source warehouse only
         │
         └─ Group: Full (inherits Source Only)
             ├─ Inherits: All Source Only restrictions
             └─ Validates: Source + Destination warehouses
```

**Group Inheritance Chain:**
```
Base (Cybrosys) → Source Only (Econovo) → Full (Econovo)
```

This inheritance ensures that:
- Users with "Full" automatically get all "Source Only" restrictions PLUS destination validation
- Users with "Source Only" automatically get all base module restrictions PLUS source validation
- No group conflicts (Full is always more restrictive than Source Only)



## Problem Statement

The base `user_warehouse_restriction` module provides excellent access control for stock picking types, locations, warehouses, and pickings. However, it has critical security gaps:

### Security Gaps in Base Module

1. **Stock Quants (Inventory Adjustments)**: ❌ NOT RESTRICTED
   - Users can access `Inventory → Operations → Inventory Adjustments`
   - Can view/modify stock quantities in ANY warehouse
   - Completely bypasses warehouse restrictions

2. **Stock Moves**: ❌ NOT RESTRICTED
   - Users can see all stock movements regardless of warehouse assignment

3. **Stock Move Lines**: ❌ NOT RESTRICTED
   - Detailed operation lines not filtered by warehouse access

4. **Cross-Warehouse Transfers**: ❌ NOT CONTROLLED
   - Users can transfer from allowed WH1 to prohibited WH2
   - No validation on destination warehouse

### Real-World Impact

**Scenario**: User1 assigned to Warehouse A only
- ✅ Cannot access Warehouse B via picking types (base module working)
- ❌ **CAN** create inventory adjustments in Warehouse B (SECURITY BREACH)
- ❌ **CAN** transfer stock from Warehouse A to Warehouse B (SECURITY BREACH)

## Solution

This module closes all security gaps and adds flexible control mechanisms.

### Features

#### 1. Complete Security Coverage

- ✅ **Stock Quant Restriction**: Blocks inventory adjustments in unauthorized warehouses
- ✅ **Stock Move Restriction**: Controls both source and destination access
- ✅ **Stock Move Line Restriction**: Enforces restrictions at operation level
- ✅ **Cross-Warehouse Transfer Validation**: Python constraints prevent unauthorized destinations

#### 2. Two-Level Restriction Groups (Inherited Architecture)

The module provides two security groups with inheritance:

**Group A: Warehouse Restriction - Source Only** (Base restriction level)
- **Inherits from**: `user_warehouse_restriction_group_user` (base module)
- **Validates**: Source warehouse only
- **Allows**: Transfers to ANY destination warehouse
- **Use case**: Regional managers redistributing stock from their warehouses
- **Technical**: Adds Record Rules + source validation in Python

**Group B: Warehouse Restriction - Full (Source + Destination)** (Maximum restriction)
- **Inherits from**: `Warehouse Restriction - Source Only` (which inherits from base)
- **Validates**: BOTH source AND destination warehouses
- **Blocks**: Transfers to unauthorized warehouses
- **Use case**: Warehouse operators working only within assigned warehouses
- **Technical**: Adds destination validation on top of Source Only restrictions

> **Inheritance Chain**: Base (Cybrosys) → Source Only → Full
> 
> This means users with "Full" group automatically have ALL restrictions from "Source Only" PLUS the additional destination validation. The Python constraint checks the most specific group first (Full before Source Only) to ensure proper restriction enforcement.```

### What the Base Module Provides

`user_warehouse_restriction` (Cybrosys) provides:

| Feature | Coverage |
|---------|----------|
| **Group** | `user_warehouse_restriction_group_user` (base group) |
| **Field** | `warehouse.user_ids` - Assign users to warehouses |
| **Field** | `user.allowed_warehouse_ids` - View user's assigned warehouses |
| **Field** | `user.location_ids` - Restrict specific locations (⚠️ see compatibility note) |
| **Record Rules** | stock.picking.type, stock.location, stock.warehouse, stock.picking |
| **Protection** | Prevents self-removal from warehouse assignments |

### What This Module Adds

`econovo_user_warehouse_restriction` adds:

| Feature | Description |
|---------|-------------|
| **2 Granular Groups** | Full Restriction (Source + Destination) and Source Only |
| **5 Record Rules** | stock.quant, stock.move (2 rules), stock.move.line (2 rules) |
| **Transit System** | warehouse.is_transit_warehouse, location.is_transit_location |
| **Python Validation** | stock.move._check_warehouse_transfer_permission() |
| **Closes Security Gaps** | Quants, moves, and move lines not restricted by base module |

## Problem Statement

The base `user_warehouse_restriction` module provides excellent access control for stock picking types, locations, warehouses, and pickings. However, it has critical security gaps:

### Security Gaps in Base Module (Closed by This Extension)

1. **Stock Quants (Inventory Adjustments)**: ❌ NOT RESTRICTED in base
   - Users can access `Inventory → Operations → Inventory Adjustments`
   - Can view/modify stock quantities in ANY warehouse
   - ✅ **FIXED** by this module with Record Rules

2. **Stock Moves**: ❌ NOT RESTRICTED in base
   - Users can see all stock movements regardless of warehouse assignment
   - ✅ **FIXED** by this module with Record Rules + Python constraint

3. **Stock Move Lines**: ❌ NOT RESTRICTED in base
   - Detailed operation lines not filtered by warehouse access
   - ✅ **FIXED** by this module with Record Rules

4. **Cross-Warehouse Transfers**: ❌ NOT CONTROLLED in base
   - Users can transfer from allowed WH1 to prohibited WH2
   - No validation on destination warehouse
   - ✅ **FIXED** by this module with Python constraint

### Real-World Impact (Before This Module)

**Scenario**: User1 assigned to Warehouse A only
- ✅ Cannot access Warehouse B via picking types (base module working)
- ❌ **CAN** create inventory adjustments in Warehouse B (SECURITY BREACH)
- ❌ **CAN** transfer stock from Warehouse A to Warehouse B (SECURITY BREACH)
- ❌ **CAN** see all stock movements system-wide (INFORMATION LEAK)

**After installing this module**: All gaps closed ✅

## Solution

This module closes all security gaps and adds flexible control mechanisms.

### Features

#### 1. Complete Security Coverage

- ✅ **Stock Quant Restriction**: Blocks inventory adjustments in unauthorized warehouses
- ✅ **Stock Move Restriction**: Filters movements by warehouse access
- ✅ **Stock Move Line Restriction**: Controls detailed operation visibility
- ✅ **Destination Validation**: Python constraint prevents unauthorized transfers

#### 3. Transit Warehouse Support

Enable inter-warehouse collaboration without compromising security:

**Transit Warehouse (warehouse-level)**
- Mark entire warehouse as "Transit/Shared"
- Accessible by all users for transit operations
- Perfect for central distribution hubs
- **IMPORTANT**: Must enable this flag for transit warehouses or product lines will disappear

**Transit Location (location-level)**
- Mark specific locations as "Transit/Shared"
- Useful for shared dock/staging areas
- Fine-grained control for specific workflows

**Configuration**:
```
Inventory → Configuration → Warehouses → Select Transit WH → Enable "Transit/Shared Warehouse"
Inventory → Configuration → Locations → Select Transit Loc → Enable "Transit/Shared Location"
```

**Real-World Scenario**:
```
User1 (assigned to WH1) ← → Transit Warehouse ← → User2 (assigned to WH2)

✅ User1 can: WH1 → Transit WH
✅ User2 can: Transit WH → WH2
❌ User1 CANNOT: WH1 → WH2 (direct transfer blocked)
❌ User2 CANNOT: WH1 → WH2 (direct transfer blocked)
```

> **⚠️ Common Pitfall**: Forgetting to enable `is_transit_warehouse=True` on transit warehouses will cause Record Rules to filter out stock move lines when picking locations change to transit. Always configure transit flags during warehouse setup.

#### 4. Cross-Warehouse Permissions

For users who need access to multiple warehouses:

**✅ RECOMMENDED: Use warehouse.user_ids (from base module)**
- Assign users to multiple warehouses in `Inventory → Configuration → Warehouses`
- Edit warehouse → "Allowed Users" tab → Add users
- This method is compatible with all Record Rules (base + econovo)

**❌ DO NOT USE: user.location_ids (from base module)**
- This field restricts specific locations (different purpose)
- Can conflict with econovo's warehouse-based restrictions
- If you use econovo groups, leave `location_ids` empty

## Technical Implementation

### Architecture

#### Model Extensions

1. **stock.warehouse** (`models/stock_warehouse.py`)
   - Field: `is_transit_warehouse` (Boolean)
   - Override: `write()` method for admin bypass
   - Function: `_assign_installer_to_warehouses()` for installation

2. **stock.location** (`models/stock_location.py`)
   - Field: `is_transit_location` (Boolean)
   - Enables location-level transit flagging

3. **res.users** (`models/res_users.py`)
   - No additional fields (uses base module's warehouse.user_ids)
   - Documentation for proper configuration

4. **stock.move** (`models/stock_move.py`)
   - Constraint: `_check_warehouse_transfer_permission()`
   - Validates source/destination warehouse access based on user's restriction group
   - Provides clear error messages with allowed warehouses list

### Security Rules

#### Three-Layer Security Architecture

This module implements a three-layer security system:

**Layer 1: Base Module Record Rules (SQL-level)**
- Filters: stock.picking.type, stock.location, stock.warehouse, stock.picking
- Applied automatically when users have econovo groups (inherited via implied_ids)

**Layer 2: Econovo Record Rules (SQL-level)**
- Filters: stock.quant, stock.move, stock.move.line
- Group-specific rules for "Full Restriction" and "Source Only"
- Transit support built into domains

**Layer 3: Python Constraint (Application-level)**
- Validates warehouse transfers before creation
- Group-aware validation (different logic for Full vs Source Only)
- Provides user-friendly error messages

**Execution Order:**
```
1. User attempts to create/view stock.move
2. Odoo applies Base Module Record Rules (SQL filter)
   └─ Blocks if picking/warehouse not accessible
3. Odoo applies Econovo Record Rules (SQL filter)
   └─ Blocks if source/destination not in allowed list
4. Python constraint runs (if record accessible)
   └─ Final validation with detailed error messages
```

### Record Rules Strategy

All rules use SQL-level filtering with domain logic:

```python
['|', '|', 
    ('location_id.warehouse_id.user_ids', 'in', user.id),  # Allowed warehouse
    ('location_id.warehouse_id.is_transit_warehouse', '=', True),  # Transit WH
    ('location_id.is_transit_location', '=', True)  # Transit location
]
```

#### Rules Implemented by This Module

| Model | Rule Name | Group | Validates |
|-------|-----------|-------|-----------|
| stock.quant | Stock Quant Restrict (with Transit) | Base Group | Source + Transit |
| stock.move | Stock Move - Full Restriction | Full (Source + Destination) | Source + Dest + Transit |
| stock.move | Stock Move - Source Only | Source Only | Source + Transit |
| stock.move.line | Stock Move Line - Full Restriction | Full (Source + Destination) | Source + Dest + Transit |
| stock.move.line | Stock Move Line - Source Only | Source Only | Source + Transit |

### Security Groups (XML Reference)

```xml
<!-- Group A: Full Restriction (both source and destination) -->
<record id="group_warehouse_restriction_full" model="res.groups">
    <field name="name">Warehouse Restriction - Full (Source + Destination)</field>
    <field name="implied_ids" eval="[(4, ref('user_warehouse_restriction.user_warehouse_restriction_group_user'))]"/>
</record>

<!-- Group B: Source Only (only source validated) -->
<record id="group_warehouse_restriction_source_only" model="res.groups">
    <field name="name">Warehouse Restriction - Source Only</field>
    <field name="implied_ids" eval="[(4, ref('user_warehouse_restriction.user_warehouse_restriction_group_user'))]"/>
</record>
```

### Validation Logic (stock.move) - Current Implementation

```python
@api.constrains('location_id', 'location_dest_id')
def _check_warehouse_transfer_permission(self):
    """
    Validates warehouse access for stock moves based on user group.
    Inherits base module group, adds two restriction levels.
    """
    for move in self:
        user = self.env.user
        
        # SOURCE ONLY GROUP: Validate only source warehouse
        if user.has_group('econovo_user_warehouse_restriction.group_warehouse_restriction_source_only'):
            # Validate source (with transit exceptions)
            source_warehouse = move.location_id.warehouse_id
            if source_warehouse not in allowed_warehouses:
                if not (source_warehouse.is_transit_warehouse or move.location_id.is_transit_location):
                    raise ValidationError(_("You do not have permission..."))
            # Do NOT validate destination - that's the key difference
            continue
        
        # FULL RESTRICTION GROUP: Validate both source AND destination (falls through)
        # Validate source...
        # Validate destination...
        if dest_warehouse not in allowed_warehouses:
            if not (dest_warehouse.is_transit_warehouse or dest_location.is_transit_location):
                raise ValidationError(_("You do not have permission..."))
```

## Installation

### Prerequisites

1. Odoo 17.0
2. `user_warehouse_restriction` module (Cybrosys Technologies)
3. `stock` module (Odoo core)

### Steps

1. Copy module to addons directory:
   ```bash
   cp -r econovo_user_warehouse_restriction /path/to/odoo/addons/
   ```

2. Update apps list:
   - Go to Apps menu
   - Click "Update Apps List"

3. Install module:
   - Search for "Econovo - User Warehouse Restriction Extension"
   - Click Install

### Post-Installation

The module automatically:
- Assigns the installer to all existing warehouses (prevents ValidationError)
- Creates security groups
- Applies record rules to existing data

## Configuration

### Step 1: Assign Users to Warehouses

1. Navigate to `Inventory → Configuration → Warehouses`
2. Open a warehouse
3. In the "Allowed Users" field, add users who should access this warehouse
4. Save

### Step 2: Choose Restriction Level

**Option A: Full Restriction (source + destination both validated):**
1. Go to `Settings → Users & Companies → Users`
2. Open user record
3. In "Access Rights" tab, add to group:
   - `Warehouse Restriction - Full (Source + Destination)`
4. Save

**Option B: Source Only (only source validated, any destination allowed):**
1. Go to `Settings → Users & Companies → Users`
2. Open user record
3. In "Access Rights" tab, add to group:
   - `Warehouse Restriction - Source Only`
4. Save

> **⚠️ Important**: 
> - "Full" group automatically inherits "Source Only" group (which inherits the base group)
> - "Source Only" group automatically inherits the base group `User Warehouse Restriction`
> - Do NOT manually assign multiple groups - use only the most specific group needed
> - If you assign "Full", the user automatically gets "Source Only" + base group restrictions

### Step 3: Configure Transit Warehouses (Optional)

**For inter-warehouse collaboration:**

1. **Transit Warehouse** (warehouse-level):
   - Go to `Inventory → Configuration → Warehouses`
   - Open warehouse record
   - Check "Transit/Shared Warehouse" checkbox
   - Save

2. **Transit Location** (location-level):
   - Go to `Inventory → Configuration → Locations`
   - Open location record
   - Check "Transit/Shared Location" checkbox
   - Save

### Step 4: Grant Cross-Warehouse Access (Optional)

**For users who need access to multiple warehouses:**

Use the base module's `warehouse.user_ids` field:

1. Navigate to `Inventory → Configuration → Warehouses`
2. Open each warehouse the user should access
3. In the "Allowed Users" field, add the user
4. Repeat for all warehouses
5. Save

> **✅ Recommended Method**: Use `warehouse.user_ids` (Many2many from base module) to assign users to multiple warehouses.

> **⚠️ DO NOT USE**: `user.location_ids` field (from base module) - This field restricts at the location level and can conflict with warehouse-based restrictions from econovo groups. Leave this field empty when using econovo groups.

## Use Cases

### Use Case 1: Basic Warehouse Segregation

**Scenario**: Two warehouses (North, South), two operators (John, Jane)

**Configuration**:
- Warehouse North: Allowed Users = John
- Warehouse South: Allowed Users = Jane
- Both users in "Full (Source + Destination)" group

**Result**:
- John can ONLY work in North (all operations)
- Jane can ONLY work in South (all operations)
- Neither can create adjustments or transfers in the other's warehouse

### Use Case 2: Regional Manager Redistribution

**Scenario**: Regional manager needs to redistribute stock from WH1 to multiple warehouses

**Configuration**:
- Warehouse 1: Allowed Users = Manager
- Manager in "Source Only" group

**Result**:
- Manager can view inventory in WH1 only
- Manager can transfer FROM WH1 to ANY destination (WH2, WH3, etc.)
- Manager cannot view inventory in WH2, WH3 (source restriction applies)

### Use Case 3: Inter-Warehouse Collaboration via Transit

**Scenario**: User1 (WH1) and User2 (WH2) need to exchange stock securely

**Configuration**:
- Warehouse 1: Allowed Users = User1
- Warehouse 2: Allowed Users = User2
- Transit Warehouse: Allowed Users = (empty), "Transit/Shared Warehouse" = True
- Both users in "Full (Source + Destination)" group

**Result**:
```
User1 Operations:
✅ WH1 → Transit WH (allowed)
✅ Transit WH inventory visible (transit access)
❌ WH1 → WH2 direct (blocked by constraint)
❌ WH2 inventory not visible (not assigned)

User2 Operations:
✅ Transit WH → WH2 (allowed)
✅ Transit WH inventory visible (transit access)
❌ WH1 → WH2 direct (blocked by constraint)
❌ WH1 inventory not visible (not assigned)
```

### Use Case 4: Shared Dock Location

**Scenario**: Multiple warehouses share a receiving dock

**Configuration**:
- Create location "Shared Dock"
- Check "Transit/Shared Location" on dock location
- Assign users to their respective warehouses

**Result**:
- All users can receive into Shared Dock
- Users can only transfer FROM dock to their allowed warehouses
- Provides flexible receiving without compromising warehouse segregation

## Troubleshooting

### Issue: "You cannot remove yourself from the allowed users of this warehouse"

**Cause**: Base module's `write()` method prevents self-removal

**Solution**: This module overrides the validation for:
- Superusers
- System administrators (base.group_system)
- Installation context

If you still see this error, check that you're an administrator.

### Issue: "You do not have permission to transfer stock to warehouse 'X'"

**Cause**: Validation constraint is enforcing warehouse restrictions

**Solutions**:
1. **Add user to destination warehouse**: If legitimate access needed
   - Go to destination warehouse's "Allowed Users" field
   - Add the user
2. **Change to Source Only group**: If user should redistribute FROM their warehouse to any destination
   - Change user's group to "Source Only"
3. **Mark destination as transit**: If it's a shared/collaboration warehouse
   - Enable "Transit/Shared Warehouse" on destination
4. **Assign to multiple warehouses**: For cross-warehouse access
   - Add user to `warehouse.user_ids` of all relevant warehouses

> **Note**: The `allow_cross_warehouse_transfers` field was removed in v17.0.1.0.1 due to incompatibility with base module Record Rules. Use `warehouse.user_ids` instead.

### Issue: Product lines disappear when changing picking location to transit warehouse

**Cause**: Transit warehouse missing `is_transit_warehouse=True` flag

**Symptoms**:
- Create picking with lines (e.g., DEPOS → DEPOS) ✅ Works
- Change source/destination to transit warehouse → Lines disappear ❌
- Lines reappear only after module uninstall

**Solution**:
- Navigate to `Inventory → Configuration → Warehouses`
- Open transit warehouse (e.g., "TW", "Transit", "Shared")
- Enable checkbox: **Transit/Shared Warehouse**
- Save and refresh picking

**Why this happens**: Record Rules filter `stock.move.line` based on warehouse access. Without the transit flag, lines become invisible when location changes.

### Issue: Record rules showing "Access Error" when they shouldn't

**Debugging Steps**:
1. **Check warehouse assignments**:
   - Navigate to `Inventory → Configuration → Warehouses`
   - Verify user is in "Allowed Users" field of expected warehouses
2. **Verify security group membership**:
   - Check user has correct group (Full or Source Only)
   - Verify base group inherited automatically via `implied_ids`
3. **Check transit configuration**:
   - Verify "Transit/Shared Warehouse" checkbox if warehouse should be accessible by all
   - Check "Transit/Shared Location" for shared locations
4. **Review location_ids field** (from base module):
   - If user has `location_ids` populated, this may conflict with warehouse restrictions
   - **Recommendation**: Clear `location_ids` when using econovo groups

> **⚠️ Common Issue**: Base module's `location_ids` field (location-level restriction) can conflict with this module's warehouse-level restrictions. When using econovo groups, leave `location_ids` empty and use only `warehouse.user_ids`.

### Issue: Module won't install due to ValidationError

**Cause**: Warehouses have no assigned users during installation

**Solution**: This should be handled automatically by `_assign_installer_to_warehouses()`.
If it persists:
1. Manually assign yourself to all warehouses first
2. Then install the module

## Development

### Module Structure

```
econovo_user_warehouse_restriction/
├── __init__.py
├── __manifest__.py
├── README.md
├── models/
│   ├── __init__.py
│   ├── stock_warehouse.py
│   ├── stock_location.py
│   ├── res_users.py
│   └── stock_move.py
├── security/
│   ├── econovo_user_warehouse_restriction_groups.xml
│   └── econovo_user_warehouse_restriction_security.xml
├── data/
│   └── warehouse_user_assignment.xml
└── views/
    ├── stock_warehouse_views.xml
    ├── stock_location_views.xml
    └── res_users_views.xml
```

### Testing Checklist

**Installation Tests:**
- [ ] Install module on fresh database
- [ ] Verify no ValidationError during installation
- [ ] Confirm base module is installed as dependency

**Basic Restriction Tests:**
- [ ] Assign User1 to WH1, User2 to WH2
- [ ] Add both to "Full (Source + Destination)" group
- [ ] Test User1 cannot see WH2 quants (Record Rules)
- [ ] Test User1 cannot transfer WH1 → WH2 (Python constraint)
- [ ] Test User2 cannot see WH1 quants
- [ ] Test User2 cannot transfer WH2 → WH1

**Transit System Tests:**
- [ ] Create Transit Warehouse, enable "Transit/Shared Warehouse"
- [ ] Test User1 CAN transfer WH1 → Transit
- [ ] Test User2 CAN transfer Transit → WH2
- [ ] Test User1 still CANNOT transfer WH1 → WH2 directly
- [ ] Test both users CAN see Transit warehouse inventory

**Source Only Group Tests:**
- [ ] Change User1 to "Source Only" group
- [ ] Test User1 CAN transfer WH1 → WH2 (destination not validated)
- [ ] Test User1 still CANNOT transfer WH2 → anywhere (source validated)
- [ ] Test User1 can only see WH1 inventory (Record Rules unchanged)

**Base Module Compatibility Tests:**
- [ ] Create User3 with ONLY base group (no econovo groups)
- [ ] Assign User3 to WH1 and WH2 via warehouse.user_ids
- [ ] Test User3 CAN see inventory in both warehouses
- [ ] Test User3 CAN transfer between WH1 and WH2 (no econovo restrictions)
- [ ] Test base module's write() validation prevents self-removal

**Regression Tests:**
- [ ] Verify location_ids field from base still works (when econovo groups NOT used)
- [ ] Test superuser can still remove themselves from warehouses
- [ ] Test installation doesn't break existing warehouse assignments

## Credits

### Contributors

- Jose D. Leonett (odoo@econovo.com) - Author and maintainer

### External Dependencies

- **user_warehouse_restriction** (Cybrosys Technologies) - Base module
  - Version: 17.0.2.0.2
  - License: AGPL-3

### Methodology

This module follows:
- Odoo 17 development guidelines
- Extension-based development (no base code modification)
- Security-first design principles
- Econovo coding standards

## Support

For issues, questions, or contributions:
- GitHub: https://github.com/josedleonett
- Email: odoo@econovo.com

## License

AGPL-3

Copyright (C) 2024-TODAY Jose D. Leonett

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

## Changelog

### Version 17.0.1.0.1 (2024) - Current

**Fixed**:
- 🔧 **CRITICAL**: Corrected "Source Only" group logic - now validates ONLY source warehouse (not destination)
- 🔧 **UX**: Renamed group "Full Control" → "Full (Source + Destination)" to clarify actual behavior
- 🔧 **Compatibility**: Removed `allow_cross_warehouse_transfers` field (incompatible with base module Record Rules)
- 📝 **Documentation**: Added explicit "Full Restriction" handling in Python constraint
- 📝 **Architecture**: Documented three-layer security model (Base Rules → Econovo Rules → Python)
- 📝 **README**: Complete rewrite with inheritance diagram, base module comparison, compatibility notes

**Removed**:
- ❌ `res.users.allow_cross_warehouse_transfers` field (Boolean)
- ❌ Form view extension for cross-warehouse permission checkbox
- ❌ Python bypass logic for allow_cross_warehouse_transfers

**Changed**:
- Group name: "Warehouse Restriction - Full Control" → "Warehouse Restriction - Full (Source + Destination)"
- Python constraint: Explicit handling for both groups (no more accidental fall-through)
- `res_users.py`: Now documentation-only class (recommends warehouse.user_ids from base)

**Added**:
- ⚠️ Compatibility warning: Do NOT use `location_ids` with econovo groups
- ✅ Recommendation: Use `warehouse.user_ids` for cross-warehouse access
- 📚 Documentation: "What Base Provides" vs "What Econovo Adds" comparison

### Version 17.0.1.0.0 (2024) - Initial Release

**Added**:
- Stock quant restriction with transit support
- Stock move and move line restrictions
- Flexible restriction levels (two groups: Full and Source Only)
- Transit warehouse support (warehouse-level)
- Transit location support (location-level)
- Per-user cross-warehouse transfer permission via `allow_cross_warehouse_transfers` (⚠️ later removed in v1.0.1 due to Record Rule conflicts)
- Python constraint validation for warehouse transfers
- Comprehensive UI for configuration
- Detailed error messages for validation failures

**Fixed**:
- Security gap: Inventory adjustments bypass
- Security gap: Cross-warehouse transfers bypass
- Installation ValidationError (self-removal prevention)

**Security**:
- Added record rules for stock.quant, stock.move, stock.move.line
- Implemented SQL-level filtering for performance
- Added Python constraints for business logic validation
