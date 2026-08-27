# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Log the operations whose currency will change once it becomes inferred.

    Only operations with a single-currency set of confirmed order lines that
    differs from their own currency_id are affected. Also confirm none of them
    has a manually entered amount_freight/amount_insurance, whose displayed
    currency symbol would otherwise silently change along with currency_id.
    """
    cr.execute("""
        SELECT o.id, o.name, o.currency_id, x.new_currency_id,
               o.amount_freight, o.amount_insurance
        FROM comex_operation o
        JOIN (
            SELECT line.operation_id, MIN(line.origin_currency_id) AS new_currency_id
            FROM comex_operation_product_line line
            GROUP BY line.operation_id
            HAVING COUNT(DISTINCT line.origin_currency_id) = 1
        ) x ON x.operation_id = o.id
        WHERE x.new_currency_id != o.currency_id
        ORDER BY o.id
    """)
    rows = cr.fetchall()
    _logger.info(
        "COMEX migration: %s operations will have their currency corrected to "
        "match their (single-currency) confirmed order lines.", len(rows),
    )

    at_risk = [row for row in rows if row[4] or row[5]]
    if at_risk:
        _logger.warning(
            "COMEX migration: %s of those operations have a non-zero manual "
            "amount_freight/amount_insurance, whose displayed currency symbol "
            "will change along with currency_id even though the number itself "
            "does not: %s",
            len(at_risk),
            ', '.join('%s (id=%s)' % (name, op_id) for op_id, name, *_ in at_risk),
        )
