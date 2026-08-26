# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Log the manually entered FOB amounts before amount_fob becomes computed.

    amount_fob turns into a stored compute (sum of the confirmed purchase/sale
    order lines, converted to USD). Operations with no product line at all will
    see their manually entered value replaced by 0 -- log it here as an audit
    trail before it is overwritten, since it cannot be recovered afterwards.
    """
    cr.execute("""
        SELECT o.id, o.name, o.amount_fob, o.currency_id
        FROM comex_operation o
        WHERE o.amount_fob != 0
          AND NOT EXISTS (
              SELECT 1 FROM comex_operation_product_line l
              WHERE l.operation_id = o.id
          )
        ORDER BY o.id
    """)
    rows = cr.fetchall()
    if rows:
        _logger.warning(
            "COMEX migration: %s operations with no product line have a manually "
            "entered FOB amount that will be replaced by the computed value (0, "
            "since there is nothing to compute from). Recorded here for reference: "
            "%s",
            len(rows),
            ', '.join('%s (id=%s): %s %s' % (name, op_id, amount, currency_id)
                      for op_id, name, amount, currency_id in rows),
        )
