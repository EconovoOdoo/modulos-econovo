# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Run a full product line resynchronisation.

    Synchronisation is no longer triggered on read, and sale order lines are now
    mirrored as product lines, so existing operations need one explicit pass.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    _logger.info("COMEX migration: resynchronising product lines.")
    env['comex.operation.product.line']._cron_sync_all_operations()
