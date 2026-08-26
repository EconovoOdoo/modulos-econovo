# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Force the recomputation of the new/changed FOB fields.

    price_subtotal_usd is a brand new field, and amount_fob switches from a
    manually entered value to a computed one: both need every existing record
    recomputed with the real data instead of waiting for an unrelated write.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})

    lines = env['comex.operation.product.line'].search([])
    _logger.info("COMEX migration: computing the USD subtotal of %s product lines.", len(lines))
    lines._compute_price_subtotal_usd()
    lines.flush_recordset(['price_subtotal_usd'])

    operations = env['comex.operation'].search([])
    _logger.info("COMEX migration: computing the FOB amount of %s operations.", len(operations))
    operations._compute_amount_fob()
    operations.flush_recordset(['amount_fob', 'amount_fob_usd'])
