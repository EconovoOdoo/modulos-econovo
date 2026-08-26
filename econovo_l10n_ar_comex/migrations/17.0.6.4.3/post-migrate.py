# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Recompute amount_fob with the corrected, per-line conversion.

    It used to round-trip the USD total back through the operation currency
    using the OPERATION's own date, applying a second exchange rate on top of
    each line's own one whenever the linked order's date differed from the
    operation's date -- drifting away from the source document even when the
    line was already in the operation's own currency.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    operations = env['comex.operation'].search([])
    _logger.info("COMEX migration: recomputing the FOB amount of %s operations.", len(operations))
    operations._compute_amount_fob()
    operations.flush_recordset(['amount_fob', 'amount_fob_usd'])
