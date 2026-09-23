# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    'name': "Sale Project Task Generation For Non-Service Products",
    'summary': "Generate a project and/or task from the Sale Order for consumable and "
               "storable products, not only services",
    'description': """
Sale Project Task Generation For Non-Service Products
=======================================================

Odoo only lets a product generate a Project/Task from a Sale Order line
(the native "Create on Order" / ``service_tracking`` option) when its
Product Type is *Service*. Consumable and storable products have no way to
trigger that same tracking, even when the business also wants to follow up
work (installation, assembly, delivery coordination, ...) tied to selling a
physical product.

This module lifts that restriction: the native "Create on Order" field
becomes available on every product type, and the existing ``sale_project``
generation logic (project/task creation, milestones, analytic distribution,
Sales Order smart buttons, Timesheets hour allocation if ``sale_timesheet``
is installed) is reused as-is for consumable/storable products too.

Features:
---------
* "Create on Order" (Service Tracking) field shown and editable on any
  product type, not only Service
* Same 4 options as native services: Nothing / Task (existing project) /
  Project & Task (new project) / Project (new project, no task)
* Product Type can be changed afterwards without silently resetting the
  configured tracking option
* "Projects"/"Tasks" smart buttons on the Sale Order show up for orders
  generated from tracked non-service lines too
* Once a project/task has been generated, the product can no longer be
  swapped on the confirmed line (same safeguard already applied to
  services)
* ``sale_stock`` forces "Stock Moves" as the delivered-quantity method for
  every Consumable/Storable product regardless of tracking; kept on a tracked
  non-service line, this adds a wide, pointless recompute-trigger surface to
  ``qty_to_invoice``/``invoice_status`` (any change on the line's stock moves
  re-dirties them) that interacts badly with their own related-field
  recompute cascade, causing "Amount to invoice" to intermittently freeze at
  0. Tracked non-service lines are now kept on "Manual" instead, exactly like
  a real service, removing that extra trigger surface

Requirements:
-------------
* Module ``sale_project`` (core)
* Module ``sale_stock`` (core)
    """,
    'author': "Jose D. Leonett",
    'website': 'https://github.com/josedleonett',
    'category': 'Sales/Sales',
    'version': '17.0.1.1.0',
    'license': 'AGPL-3',
    'depends': [
        'sale_project',
        'sale_stock',
    ],
    'data': [
        'views/product_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
