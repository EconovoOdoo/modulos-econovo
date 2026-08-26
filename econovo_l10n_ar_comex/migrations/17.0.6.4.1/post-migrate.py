# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Populate origin_currency_id, a brand new stored field.

    price_subtotal used to be tagged with the OPERATION's currency, which is
    wrong whenever the line's own purchase/sale order is denominated in a
    different currency: the number was always correct (copied straight from the
    order line), only its displayed currency symbol was misleading.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    lines = env['comex.operation.product.line'].search([])
    _logger.info("COMEX migration: computing the origin currency of %s product lines.", len(lines))
    lines._compute_origin_currency_id()
    lines.flush_recordset(['origin_currency_id'])

    cr.execute("""
        SELECT COUNT(*)
        FROM comex_operation_product_line line
        JOIN comex_operation operation ON operation.id = line.operation_id
        WHERE line.origin_currency_id IS DISTINCT FROM operation.currency_id
    """)
    _logger.info(
        "COMEX migration: %s product lines were mislabeled with the operation's "
        "currency instead of their own purchase/sale order's currency.",
        cr.fetchone()[0],
    )
