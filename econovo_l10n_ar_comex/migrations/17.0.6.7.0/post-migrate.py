# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Populate price_unit_usd, a brand new stored field.

    price_unit itself switches from Float to Monetary (same column type, no
    schema change to its values), so only the new USD column needs computing.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    lines = env['comex.operation.product.line'].search([])
    _logger.info("COMEX migration: computing the USD unit price of %s product lines.", len(lines))
    lines._compute_price_unit_usd()
    lines.flush_recordset(['price_unit_usd'])
