# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    'name': "Stock Picking Batch Signature",
    'summary': "Capture a signature on Batch Transfers from the desktop interface",
    'description': """
Stock Picking Batch Signature
==============================

stock.picking.batch has no signature capability at all in the desktop
interface (unlike stock.picking, which has a native "Sign" widget). This
module adds one.

Features:
---------
* "Firmar" widget on the Batch Transfer form (reuses the
  signature_signer widget from econovo_remito_digital, so the typed
  signer name is captured too)
* Represents a single custody handoff for the whole batch (e.g. a
  carrier picking up several transfers, possibly for different
  customers), NOT a per-customer proof of delivery: signing a batch
  copies the same signature/signed_by/signature_date onto every
  stock.picking it contains
* The Batch Transfer PDF report (stock_picking_batch.report_picking_batch)
  now shows the registered signature, signer name and date
* The same report also shows, hidden when there are none, the Purchase
  Order(s) behind a "Resupply Subcontractor" transfer: once printed and
  sent along with the components, the subcontractor can reference the
  exact PO on their return shipment, so it can be matched to the right
  order on receipt

Requirements:
-------------
* Module `stock_picking_batch` (core)
* Module `econovo_remito_digital` (provides the signature_signer widget)
* Module `mrp_subcontracting` (Enterprise, provides the subcontracting MO
  <-> incoming shipment link)
* Module `purchase_stock` (provides the incoming shipment <-> Purchase
  Order link)
    """,
    'author': "Jose D. Leonett",
    'website': 'https://github.com/josedleonett',
    'category': 'Inventory/Inventory',
    'version': '17.0.2.0.0',
    'license': 'AGPL-3',
    'depends': [
        'stock_picking_batch',
        'econovo_remito_digital',
        'mrp_subcontracting',
        'purchase_stock',
    ],
    'data': [
        'views/stock_picking_batch_views.xml',
        'views/report_picking_batch_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
