# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Recompute the last delivery contact.

    It used to take the last validated transfer of the units, which reported the
    supplier for goods still travelling the COMEX chain. Stored values need to be
    refreshed with the corrected criteria.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    lines = env['comex.operation.product.line'].search([])
    _logger.info("COMEX migration: recomputing the position of %s product lines.", len(lines))
    lines._refresh_stock_position_cache()
    lines.flush_recordset()

    cr.execute("""
        SELECT COUNT(*)
        FROM comex_operation_product_line
        WHERE last_delivery_partner_id IS NOT NULL
    """)
    _logger.info("COMEX migration: %s product lines with a delivery contact.", cr.fetchone()[0])
