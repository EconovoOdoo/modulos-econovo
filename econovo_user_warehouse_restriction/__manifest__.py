# -*- coding: utf-8 -*-
{
    "name": "Econovo - User Warehouse Restriction",
    "version": "17.0.1.0.0",
    "category": "Warehouse",
    "summary": "Granular warehouse access control with permission matrix (10 flags per user/warehouse)",
    "description": """
Econovo User Warehouse Restriction
===================================

Comprehensive warehouse access control system with granular permission matrix.

Permission Matrix System:
--------------------------
10 granular permission flags per user, per warehouse:

**Special Modes:**
- Full Control: Administrator mode (auto-enables all 10 flags)
- View Only: Read-only access (blocks all write operations)

**Warehouse-Level Permissions:**
- Allow as Source: Use warehouse as stock source (outbound transfers)
- Allow as Destination: Use warehouse as stock destination (inbound transfers)
- Allow Inventory Adjustment: Perform inventory adjustments (stock corrections)

**Operation-Level Permissions:**
- Allow Create Picking: Create new pickings (initiate transfers)
- Allow Write Picking: Modify existing pickings (edit draft transfers)
- Allow Delete Picking: Delete pickings (cancel transfers)

**Location Restrictions:**
- Blocked Locations: Per-warehouse location blacklist (exclude QC, High Value zones)
- Allow Transit: Bypass transit location restrictions (shared transit areas)

Key Features:
-------------
- Granular Control: 10 permission flags per user, per warehouse
- Per-Warehouse Blacklist: Location restrictions specific to each warehouse
- Special Modes: Full Control & View Only for quick configuration
- Transit Control: Per-user transit location bypass
- Flexible Matrix: Different permissions per warehouse for same user

Use Cases:
----------

**Full Control (Single Warehouse):**
- Scenario: Warehouse operator with complete access to WH1
- Configuration: full_control=True
- Result: All 10 permissions enabled for WH1

**Source Only (Redistribute Stock):**
- Scenario: Regional manager can redistribute stock FROM WH1
- Configuration: allow_as_source=True, allow_as_destination=False, allow_create_picking=True
- Result: Can move stock OUT of WH1, but cannot receive INTO WH1

**View Only (Auditor):**
- Scenario: Auditor needs read-only access
- Configuration: view_only=True
- Result: Can view all records, cannot create/modify/delete

**Quality Control Restrictions:**
- Scenario: Warehouse operator cannot access QC zone
- Configuration: full_control=True, blocked_location_ids=[WH1/QC Zone]
- Result: Full access to WH1 EXCEPT QC zone

**Multi-Warehouse (Different Permissions):**
- Scenario: Supervisor with different permissions per warehouse
- Configuration: WH1 (full_control=True), WH2 (allow_as_source=True), WH3 (view_only=True)
- Result: Granular control across multiple warehouses

Configuration:
--------------

**Method 1: Per-Warehouse Configuration**
1. Go to Inventory > Configuration > Warehouses
2. Select a warehouse
3. Click "User Permissions" tab
4. Add users with granular permission flags

**Method 2: Centralized Matrix View**
1. Go to Inventory > Configuration > User Warehouse Permissions
2. View/edit all permissions in a matrix table
3. Filter by user, warehouse, or permission flags

Security Architecture:
----------------------

**Record Rules (8 total):**
1. warehouse.user.permission - Permission matrix access control
2. stock.picking.type - Operation types by warehouse permissions
3. stock.location - Location access restrictions
4. stock.warehouse - Warehouse access by permission existence
5. stock.picking - Transfers by warehouse permissions
6. stock.quant - Inventory quants by warehouse + transit
7. stock.move - Moves by source/destination permissions
8. stock.move.line - Move lines by source/destination permissions

**Python Constraints:**
- stock.move._check_warehouse_transfer_permission()
  - Hierarchical validation: Warehouse access > Location blacklist > Transit bypass
  - Uses permission.has_source_permission(), has_destination_permission()
  - Checks blocked_location_ids with allow_transit bypass

**Domain Restrictions:**
- stock.picking._onchange_location_id()
  - Filters source locations (allow_as_source=True)
  - Filters destination locations (allow_as_destination=True)
  - Excludes blocked_location_ids from dropdowns

Technical Implementation:
-------------------------

**Model Extensions:**
- warehouse.user.permission: Core permission matrix model (10 flags)
- stock.warehouse: user_permission_ids (One2many)
- res.users: warehouse_permission_ids (One2many)
- stock.move: _check_warehouse_transfer_permission constraint
- stock.picking: _onchange_location_id domain restriction

**Validation Layers:**
1. Record Rules (SQL-level, performance optimized)
2. Python Constraints (permission matrix business logic)
3. Onchange Methods (UI-level domain filtering)

Changelog:
----------

v17.0.1.0.0 (2025-11-22) - INITIAL RELEASE:
- ADDED: warehouse.user.permission model (10 flags per user/warehouse)
- ADDED: Special modes (Full Control, View Only)
- ADDED: Per-warehouse location blacklist
- ADDED: Transit location bypass
- ADDED: 8 record rules with permission matrix
- ADDED: Python constraints for warehouse transfer validation
- ADDED: Centralized permission matrix view
- ADDED: Per-warehouse permission configuration

Author: Jose D. Leonett
Website: https://github.com/josedleonett
License: AGPL-3
""",
    "author": "Jose D. Leonett",
    "website": "https://github.com/josedleonett",
    "license": "AGPL-3",
    "depends": ["stock_sms", "stock"],
    "data": [
        # Security (groups > access > record rules)
        "security/econovo_user_warehouse_restriction_groups.xml",
        "security/ir.model.access.csv",
        "security/econovo_user_warehouse_restriction_security.xml",
        
        # Views (warehouse > permissions > users)
        "views/stock_warehouse_views.xml",
        "views/warehouse_user_permission_views.xml",
        "views/stock_location_views.xml",
        "views/res_users_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "auto_install": False,
    "application": False,
}