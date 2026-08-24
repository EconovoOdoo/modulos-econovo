# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Purchase - Repurchase from Customer',
    'version': '17.0.1.0.0',
    'summary': 'Receipts flagged as a repurchase take the goods back from the customer location.',
    'description': '''
Lets a receipt buy back goods **from the customer location** instead of the
vendor location, so repurchasing an item that was previously sold clears the
balance left behind by the original delivery.

Problem it solves
-----------------
When an item sold to a dealer is later bought back from that same dealer as a
regular purchase, Odoo moves it in from `Partners/Vendors` while the original
delivery left a balance in `Partners/Customers`. Those two virtual locations
are never netted against each other, so the item stays recorded as delivered to
a customer *and* available in stock at the same time.

For serial-tracked products this is not just cosmetic: the next delivery of that
serial number is rejected by `stock.quant.check_quantity()` with "The serial
number has already been assigned", because validating it would leave 2 units of
the same serial in the customer location.

Why the operation type alone is not enough
------------------------------------------
`purchase.order._prepare_picking()` and
`purchase.order.line._prepare_stock_move_vals()` both hardcode the source
location to `res.partner.property_stock_supplier`. That value is passed
explicitly to `create()`, which bypasses `stock.picking._compute_location_id()`
- so the `default_location_src_id` of the operation type is ignored for any
receipt generated from a purchase order (the destination is honoured, the
source is not).

Solution
--------
Adds a "Repurchase from Customer" flag on incoming operation types. When a
purchase order uses such an operation type, its receipt and the underlying
stock moves are sourced from the partner's customer location instead of the
vendor location. Nothing else about the purchase flow changes: the order, the
vendor bill and the valuation stay exactly as they are.

The flag is opt-in per operation type, so regular purchases from the same
contact are unaffected.
    ''',
    'author': 'Jose D. Leonett',
    'website': 'https://github.com/josedleonett',
    'license': 'AGPL-3',
    'category': 'Inventory/Purchase',
    'depends': [
        'purchase_stock',
    ],
    'data': [
        'views/stock_picking_type_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
