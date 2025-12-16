# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

_logger = logging.getLogger(__name__)


def _post_init_hook(env):
    """Create valuation records for existing count history records."""
    _logger.info("Creating valuation records for existing count history...")
    
    CountHistory = env['stock.quant.count.history']
    histories = CountHistory.search([])
    
    if not histories:
        _logger.info("No existing count history records found.")
        return
    
    count = 0
    for history in histories:
        try:
            history._create_valuation()
            count += 1
        except Exception as e:
            _logger.warning(
                "Failed to create valuation for count history %s: %s",
                history.id, str(e)
            )
    
    _logger.info("Created %s valuation records for existing count history.", count)
