# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Purchase Order Type - Default Operation Type',
    'version': '17.0.1.0.0',
    'summary': "Preset the receipt Operation Type (Deliver To) on each Purchase Order Type.",
    'description': '''
Lets each Purchase Order Type carry its own default receipt **Operation Type**
("Deliver To"), so selecting a type on a purchase order also applies the
operation type it was configured with.

Problem it solves
------------------
`purchase_order_type` (OCA) already lets a Purchase Order Type preset the
Payment Terms and the Incoterm onto the order, but has no way to preset the
receipt Operation Type. Companies that route different kinds of purchases
(for example regular purchases vs. COMEX/import) through dedicated
warehouses/operation types have to remember to pick the right one by hand on
every single order.

Solution
--------
Adds an optional Deliver To field on Purchase Order Type, restricted to
receipt operation types of the same company as the type. When the order's
Type is set (manually, or automatically from the partner's default type),
the existing onchange that already copies Payment Terms/Incoterm from the
type now also copies this Operation Type onto the order, the same way.

The preset is only applied interactively (onchange), like the pre-existing
Payment Terms/Incoterm preset - it never overrides an Operation Type already
computed by automated flows (reordering rules, MRP, etc.).
    ''',
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'category': 'Inventory/Purchase',
    'depends': [
        'purchase_order_type',
        'purchase_stock',
    ],
    'data': [
        'views/purchase_order_type_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
