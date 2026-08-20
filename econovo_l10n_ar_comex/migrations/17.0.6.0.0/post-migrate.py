# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Link the historical stock moves of serial-tracked products to their line.

    stock.move.comex_product_line_id is only filled going forward, so the
    machines already imported would have no traceable location until they move
    again. Untracked products are deliberately left out: they are located
    through the operation/product fallback instead.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    lines = env['comex.operation.product.line'].search([
        ('product_id.tracking', 'in', ('serial', 'lot')),
    ])
    _logger.info("COMEX migration: linking stock moves of %s tracked lines.", len(lines))
    lines._assign_stock_moves()

    cr.execute("SELECT COUNT(*) FROM stock_move WHERE comex_product_line_id IS NOT NULL")
    _logger.info("COMEX migration: %s stock moves linked to a product line.", cr.fetchone()[0])
