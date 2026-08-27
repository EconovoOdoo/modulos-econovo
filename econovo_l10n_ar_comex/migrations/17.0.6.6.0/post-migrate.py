# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Infer the currency of existing operations from their confirmed orders.

    currency_id switches from a plain manual field to a computed one: existing
    records keep their old stored value until something forces a recompute.
    amount_fob/amount_fob_usd and currency_mismatch are recomputed right after,
    since they depend on currency_id.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    operations = env['comex.operation'].search([])
    _logger.info("COMEX migration: inferring the currency of %s operations.", len(operations))
    operations._compute_currency_id()
    operations.flush_recordset(['currency_id'])

    operations._compute_amount_fob()
    operations._compute_currency_mismatch()
    operations.flush_recordset(['amount_fob', 'amount_fob_usd', 'currency_mismatch'])

    cr.execute("SELECT COUNT(*) FROM comex_operation WHERE currency_mismatch")
    _logger.info(
        "COMEX migration: %s operations still have a genuine currency mix among "
        "their orders and remain flagged/manual.", cr.fetchone()[0],
    )
