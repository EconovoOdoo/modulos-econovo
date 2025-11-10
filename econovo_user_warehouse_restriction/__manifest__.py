# -*- coding: utf-8 -*-
{
    'name': 'Econovo - User Warehouse Restriction Extension',
    'version': '17.0.1.0.0',
    'category': 'Warehouse',
    'summary': 'Extends User Warehouse Restriction to include Stock Quant and Move restrictions',
    'description': """
Econovo User Warehouse Restriction Extension
=============================================

This module extends the base `user_warehouse_restriction` module to provide
comprehensive warehouse access control with flexible restriction levels and
transit warehouse support for inter-warehouse collaboration.

Security Enhancements:
---------------------
The base module restricts access to stock picking types, locations, warehouses,
and pickings. This extension adds critical missing restrictions for:

* **Stock Quants** (inventory adjustments) - Prevents bypass via Inventory menu
* **Stock Moves** (stock movements) - Controls source and destination access
* **Stock Move Lines** (detailed operations) - Enforces restrictions at operation level

Key Features:
-------------

1. **Flexible Restriction Levels**:
   * **Full Control**: Both source AND destination must be in allowed warehouses
     - Use case: Warehouse operators who should only work within their assigned warehouse
   
   * **Source Only**: Only source restricted, any destination allowed
     - Use case: Regional managers redistributing stock across multiple warehouses

2. **Transit Warehouse Support**:
   * Mark warehouses as "Transit/Shared" for inter-warehouse collaboration
   * Mark locations as "Transit/Shared" for temporary stock staging
   * Enables User1 (WH1) → Transit WH → User2 (WH2) workflows
   * Blocks direct User1 → WH2 transfers while allowing transit routes

3. **Per-User Cross-Warehouse Permission**:
   * Individual users can be granted cross-warehouse transfer capability
   * Bypasses destination restrictions while maintaining source control
   * Flexible for managers needing broader access

Technical Implementation:
-------------------------
* Extends base module via proper inheritance (no code modification)
* Uses Odoo's native Record Rules (ir.rule) for SQL-level security
* Python constraints for business logic validation
* Domain logic: ['|', (allowed_wh), '|', (transit_wh), (transit_loc)]
* Performance optimized (SQL filtering, no Python loops)

Security Groups:
----------------
* **Warehouse Restriction - Full Control**: Source + Destination restricted
* **Warehouse Restriction - Source Only**: Only source restricted

Configuration:
--------------
1. Assign users to warehouses via Inventory → Configuration → Warehouses
2. Choose restriction level by adding users to appropriate group
3. Mark warehouses/locations as "Transit" if needed for collaboration
4. Grant "Allow Cross-Warehouse Transfers" to specific users if needed

Real-World Scenario:
--------------------
User1 manages WH1, User2 manages WH2. They need to exchange stock:
- Create Transit Warehouse (TW) and mark as "Transit/Shared"
- User1: Can transfer WH1 → TW ✅, Cannot transfer WH1 → WH2 ❌
- User2: Can transfer TW → WH2 ✅, Cannot transfer WH1 → WH2 ❌
- Result: Secure inter-warehouse collaboration via controlled transit point

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
    'installable': True,
    'auto_install': False,
    'application': False,
}
