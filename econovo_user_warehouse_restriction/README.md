# Econovo - User Warehouse Restriction Extension

## Overview

This module extends the `user_warehouse_restriction` module (by Cybrosys Technologies) to provide comprehensive warehouse access control with flexible restriction levels and transit warehouse support for inter-warehouse collaboration.

## Version

- **Module Version**: 17.0.1.0.0
- **Odoo Version**: 17.0
- **Author**: Jose D. Leonett
- **License**: AGPL-3

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

#### 2. Flexible Restriction Levels

Two security groups provide different restriction strategies:

**Group A: Warehouse Restriction - Full Control**
- BOTH source AND destination must be in allowed warehouses
- Cannot transfer to unauthorized warehouses
- Use case: Warehouse operators who should only work within their assigned warehouse

**Group B: Warehouse Restriction - Source Only**
- ONLY source location must be in allowed warehouses
- CAN transfer to ANY destination warehouse
- Use case: Regional managers redistributing stock across multiple warehouses

#### 3. Transit Warehouse Support

Enable inter-warehouse collaboration without compromising security:

**Transit Warehouse (warehouse-level)**
- Mark entire warehouse as "Transit/Shared"
- Accessible by all users for transit operations
- Perfect for central distribution hubs

**Transit Location (location-level)**
- Mark specific locations as "Transit/Shared"
- Useful for shared dock/staging areas
- Fine-grained control for specific workflows

**Real-World Scenario**:
```
User1 (assigned to WH1) ← → Transit Warehouse ← → User2 (assigned to WH2)

✅ User1 can: WH1 → Transit WH
✅ User2 can: Transit WH → WH2
❌ User1 CANNOT: WH1 → WH2 (direct transfer blocked)
❌ User2 CANNOT: WH1 → WH2 (direct transfer blocked)
```

#### 4. Per-User Cross-Warehouse Permission

- Field: `allow_cross_warehouse_transfers` on `res.users`
- Grants individual users ability to transfer to any destination
- Bypasses destination restrictions while maintaining source control
- Flexible for managers needing broader access

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
   - Field: `allow_cross_warehouse_transfers` (Boolean)
   - Per-user permission control

4. **stock.move** (`models/stock_move.py`)
   - Constraint: `_check_warehouse_transfer_permission()`
   - Validates destination warehouse access
   - Provides clear error messages

### Security Rules

#### Record Rules Strategy

All rules use SQL-level filtering with domain logic:

```python
['|', '|', 
    ('location_id.warehouse_id.user_ids', 'in', user.id),  # Allowed warehouse
    ('location_id.warehouse_id.is_transit_warehouse', '=', True),  # Transit WH
    ('location_id.is_transit_location', '=', True)  # Transit location
]
```

#### Rules Implemented

| Model | Rule Name | Group | Logic |
|-------|-----------|-------|-------|
| stock.quant | Stock Quant Restrict (with Transit) | Base Group | Allowed + Transit |
| stock.move | Stock Move - Full Restriction | Full Control | Source + Dest + Transit |
| stock.move | Stock Move - Source Only | Source Only | Source + Transit |
| stock.move.line | Stock Move Line - Full Restriction | Full Control | Source + Dest + Transit |
| stock.move.line | Stock Move Line - Source Only | Source Only | Source + Transit |

### Security Groups

```xml
<!-- Full Control: Source + Destination restricted -->
<record id="group_warehouse_restriction_full" model="res.groups">
    <field name="name">Warehouse Restriction - Full Control</field>
    <field name="implied_ids" eval="[(4, ref('user_warehouse_restriction.user_warehouse_restriction_group_user'))]"/>
</record>

<!-- Source Only: Only source restricted -->
<record id="group_warehouse_restriction_source_only" model="res.groups">
    <field name="name">Warehouse Restriction - Source Only</field>
    <field name="implied_ids" eval="[(4, ref('user_warehouse_restriction.user_warehouse_restriction_group_user'))]"/>
</record>
```

### Validation Logic (stock.move)

```python
@api.constrains('location_id', 'location_dest_id')
def _check_warehouse_transfer_permission(self):
    for move in self:
        # Skip if user has cross-warehouse permission
        if user.allow_cross_warehouse_transfers:
            continue
        
        # Skip if user is in Source Only group
        if user.has_group('group_warehouse_restriction_source_only'):
            continue
        
        # Skip if destination is transit
        if dest_warehouse.is_transit_warehouse or dest_location.is_transit_location:
            continue
        
        # Validate destination warehouse access
        if dest_warehouse not in allowed_warehouses:
            raise ValidationError("Permission denied...")
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

**For Full Control (source + destination restricted):**
1. Go to `Settings → Users & Companies → Users`
2. Open user record
3. In "Access Rights" tab, add to group:
   - `Warehouse Restriction - Full Control`

**For Source Only (only source restricted):**
1. Same as above, but add to group:
   - `Warehouse Restriction - Source Only`

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

### Step 4: Grant Cross-Warehouse Permission (Optional)

**For specific users who need broader access:**

1. Go to `Settings → Users & Companies → Users`
2. Open user record
3. In "Preferences" tab, find "Warehouse Permissions" section
4. Check "Allow Cross-Warehouse Transfers"
5. Save

## Use Cases

### Use Case 1: Basic Warehouse Segregation

**Scenario**: Two warehouses (North, South), two operators (John, Jane)

**Configuration**:
- Warehouse North: Allowed Users = John
- Warehouse South: Allowed Users = Jane
- Both users in "Full Control" group

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
- Both users in "Full Control" group

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

**Cause**: Validation constraint is working correctly

**Solutions**:
1. **Add user to destination warehouse**: If legitimate access needed
2. **Change to Source Only group**: If user should redistribute stock
3. **Enable cross-warehouse transfers**: For individual user exception
4. **Mark destination as transit**: If it's a shared warehouse

### Issue: Record rules showing "Access Error" when they shouldn't

**Debugging**:
1. Check user's warehouse assignments
2. Verify security group membership
3. Check if destination is marked as transit
4. Review `allow_cross_warehouse_transfers` setting

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

- [ ] Install module on fresh database
- [ ] Verify no ValidationError during installation
- [ ] Assign User1 to WH1, User2 to WH2
- [ ] Test User1 cannot see WH2 quants
- [ ] Test User1 cannot transfer WH1 → WH2
- [ ] Create Transit Warehouse
- [ ] Test User1 CAN transfer WH1 → Transit
- [ ] Test User2 CAN transfer Transit → WH2
- [ ] Test User1 still CANNOT transfer WH1 → WH2
- [ ] Test Source Only group allows any destination
- [ ] Test cross-warehouse permission bypasses validation

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

### Version 17.0.1.0.0 (2024)

**Added**:
- Stock quant restriction with transit support
- Stock move and move line restrictions
- Flexible restriction levels (Full Control vs Source Only)
- Transit warehouse support (warehouse-level)
- Transit location support (location-level)
- Per-user cross-warehouse transfer permission
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
