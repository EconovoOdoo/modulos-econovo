# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import SUPERUSER_ID
from odoo.api import Environment


def migrate(cr, version):
    """Fix pre-existing lines stuck on the wrong delivered-qty method.

    Before this version, tracked non-service (consu/product) lines were left
    on ``qty_delivered_method='stock_move'`` by ``sale_stock``. That extra,
    unneeded dependency on stock moves is what let ``qty_to_invoice``/
    ``invoice_status`` intermittently freeze at 0 on already-confirmed
    orders. The new ``_compute_qty_delivered_method`` override only affects
    records recomputed from now on, so existing rows must be forced through
    the full chain once here.
    """
    env = Environment(cr, SUPERUSER_ID, {})
    lines = env['sale.order.line'].search([
        ('product_id.type', '!=', 'service'),
        ('product_id.service_tracking', '!=', 'no'),
    ])
    if not lines:
        return
    lines._compute_qty_delivered_method()
    lines._compute_qty_delivered()
    lines._compute_qty_to_invoice()
    lines._compute_invoice_status()
    lines.flush_recordset([
        'qty_delivered_method', 'qty_delivered', 'qty_to_invoice', 'invoice_status',
    ])
