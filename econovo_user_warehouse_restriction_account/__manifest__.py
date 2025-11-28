# -*- coding: utf-8 -*-
{
    "name": "Econovo - User Warehouse Restriction (Stock Account)",
    "version": "17.0.1.0.0",
    "category": "Inventory",
    "summary": "Extends warehouse restriction to stock valuation layers",
    "description": """
Bridge module that extends econovo_user_warehouse_restriction to support
stock.valuation.layer model from stock_account.

This module installs automatically when both:
- econovo_user_warehouse_restriction
- stock_account
are installed.

It adds security rules to restrict access to valuation layers based on
warehouse permissions.
    """,
    "author": "Jose D. Leonett",
    "website": "https://github.com/josedleonett",
    "license": "AGPL-3",
    "depends": [
        "econovo_user_warehouse_restriction",
        "stock_account",
    ],
    "data": [
        "security/security.xml",
    ],
    "auto_install": True,  # KEY: Installs automatically when BOTH depends are installed
    "installable": True,
    "application": False,
}
