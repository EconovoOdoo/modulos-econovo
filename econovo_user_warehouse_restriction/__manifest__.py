# -*- coding: utf-8 -*-
{
    'name': 'Econovo - User Warehouse Restriction Extension',
    'version': '17.0.1.1.0',
    'category': 'Warehouse',
    'summary': 'Extends User Warehouse Restriction with Stock Quant/Move controls and flexible restriction levels',
    'description': """
Econovo User Warehouse Restriction Extension
=============================================

This module extends the base `user_warehouse_restriction` module (Cybrosys Technologies)
to provide comprehensive warehouse access control with flexible restriction levels and
transit warehouse support for inter-warehouse collaboration.

Architecture:
-------------
Base Module Provides:
    - 1 security group (User Warehouse Restriction)
    - warehouse.user_ids field (M2M: users assigned to warehouses)
    - 4 Record Rules for stock.picking.type, stock.location, stock.warehouse, stock.picking
    - write() validation preventing self-removal from warehouses

This Extension Adds (via Group Inheritance):
    - 2 granular groups with inheritance chain:
      * Source Only (inherits base group) - validates source warehouse only
      * Full (inherits Source Only) - validates source + destination warehouses
    - 5 Record Rules filling security gaps: stock.quant, stock.move (x2), stock.move.line (x2)
    - Transit system: is_transit_warehouse, is_transit_location flags
    - Python constraint: group-aware validation logic (checks most specific group first)

Group Inheritance Chain:
    Base (Cybrosys) → Source Only (Econovo) → Full (Econovo)

Security Enhancements:
---------------------
The base module restricts access to picking types, locations, warehouses,
and pickings. This extension adds critical missing restrictions for:

* **Stock Quants** (inventory adjustments) - Prevents bypass via Inventory menu
* **Stock Moves** (stock movements) - Controls source/destination with group-specific logic
* **Stock Move Lines** (detailed operations) - Enforces restrictions at operation level

Key Features:
-------------

1. **Two-Level Restriction Groups** (both inherit base group):
   
   * **Full (Source + Destination)**: Both source AND destination must be in allowed warehouses
     - Use case: Warehouse operators who should only work within their assigned warehouse
     - Validation: Checks BOTH move.location_id AND move.location_dest_id warehouses
   
   * **Source Only**: Only source restricted, any destination allowed
     - Use case: Regional managers redistributing stock from their warehouse to others
     - Validation: Checks ONLY move.location_id warehouse, destination unrestricted

2. **Transit Warehouse System**:
   * Mark warehouses as "Transit/Shared" for inter-warehouse collaboration
   * Mark locations as "Transit/Shared" for temporary stock staging
   * Enables User1 (WH1) → Transit WH → User2 (WH2) workflows
   * Blocks direct User1 → WH2 transfers while allowing controlled transit routes

3. **Cross-Warehouse Access** (use base module field):
   * Assign users to multiple warehouses via warehouse.user_ids (M2M)
   * Recommended for managers needing access to multiple warehouses
   * ⚠️ DO NOT use user.location_ids (from base) - conflicts with warehouse-based restrictions

Technical Implementation:
-------------------------
* Extends base module via proper inheritance (no base code modification)
* Three-layer security: Base Record Rules → Econovo Record Rules → Python Constraint
* Uses Odoo's native ir.rule for SQL-level security (performance optimized)
* Python constraints for group-aware business logic validation
* Domain logic: ['|', (allowed_wh), '|', (transit_wh), (transit_loc)]

Security Groups:
----------------
* **Warehouse Restriction - Full (Source + Destination)**: Validates both source and destination
* **Warehouse Restriction - Source Only**: Validates only source, any destination allowed
  (Both groups automatically inherit: User Warehouse Restriction via implied_ids)

Configuration:
--------------
1. Assign users to warehouses via Inventory → Configuration → Warehouses → Allowed Users
2. Choose restriction level by adding users to appropriate econovo group
3. Mark warehouses/locations as "Transit" if needed for collaboration
4. For cross-warehouse access: Add user to warehouse.user_ids of all relevant warehouses

Real-World Scenario:
--------------------
User1 manages WH1, User2 manages WH2. They need to exchange stock securely:
- Create Transit Warehouse (TW) and mark as "Transit/Shared"
- Assign User1 to WH1, User2 to WH2 (via warehouse.user_ids)
- Both users in "Full (Source + Destination)" group
- User1: Can transfer WH1 → TW ✅, Cannot transfer WH1 → WH2 ❌
- User2: Can transfer TW → WH2 ✅, Cannot transfer WH1 → WH2 ❌
- Result: Secure inter-warehouse collaboration via controlled transit point

Changelog:
----------
v17.0.1.1.0 (2025-11-15):
- ADDED: Secure-by-default (least privilege) - Auto-assign Full Restriction to all users
- ADDED: post_init_hook assigns Full Restriction to existing users on install
- ADDED: res.users.create() override auto-assigns Full Restriction to new users
- ADDED: Transit warehouse configuration warnings in docs and field help text
- FIXED: Documented product lines disappearing issue when transit flag not set
- IMP: Group inheritance architecture (Full inherits Source Only inherits Base)

v17.0.1.0.1:
- FIXED: "Source Only" group now validates ONLY source (not destination)
- FIXED: Renamed "Full Control" → "Full (Source + Destination)" for clarity
- REMOVED: allow_cross_warehouse_transfers field (incompatible with base Record Rules)
- ADDED: Documentation for base module interaction and compatibility notes

Author: Jose D. Leonett
Website: https://github.com/josedleonett
License: AGPL-3
""",
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'depends': ['user_warehouse_restriction', 'stock'],
    'data': [
        'security/econovo_user_warehouse_restriction_groups.xml',
        'security/econovo_user_warehouse_restriction_security.xml',
        'data/warehouse_user_assignment.xml',
        'views/stock_warehouse_views.xml',
        'views/stock_location_views.xml',
        'views/res_users_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'auto_install': False,
    'application': False,
}
