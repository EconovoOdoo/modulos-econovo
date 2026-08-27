# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Populate the new currency_mismatch flag and log its scope.

    currency_id defaults to USD and is only ever changed by hand: an operation
    whose linked orders are all in another currency stays silently wrong unless
    someone corrects it. This does not change any amount, only surfaces a
    warning where it was invisible before.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    operations = env['comex.operation'].search([])
    _logger.info(
        "COMEX migration: checking the currency of %s operations against their "
        "linked orders.", len(operations),
    )
    operations._compute_currency_mismatch()
    operations.flush_recordset(['currency_mismatch'])

    cr.execute("SELECT COUNT(*) FROM comex_operation WHERE currency_mismatch")
    _logger.warning(
        "COMEX migration: %s operations have their own currency set differently "
        "from at least one of their linked purchase/sale orders.",
        cr.fetchone()[0],
    )
