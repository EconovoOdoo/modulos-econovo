# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Populate the materialised stock position columns.

    current_location_display, lot_name_display and last_delivery_partner_id are
    stored so they can be sorted and grouped. They have no depends, so they stay
    empty until something refreshes them.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    lines = env['comex.operation.product.line'].search([])
    _logger.info("COMEX migration: locating %s product lines.", len(lines))
    lines._refresh_stock_position_cache()
    lines.flush_recordset()

    cr.execute("""
        SELECT COUNT(*)
        FROM comex_operation_product_line
        WHERE current_location_display IS NOT NULL AND current_location_display != ''
    """)
    _logger.info("COMEX migration: %s product lines located.", cr.fetchone()[0])
