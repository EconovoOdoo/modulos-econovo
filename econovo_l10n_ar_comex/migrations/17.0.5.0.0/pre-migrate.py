# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Deduplicate COMEX product lines before the new unique constraints apply.

    comex.operation.product.line now enforces a single product line per purchase
    order line and per sale order line. The former synchronisation could create
    duplicates, which would make the module upgrade fail on the new constraints.
    """
    for column in ('purchase_line_id', 'sale_line_id'):
        cr.execute("""
            DELETE FROM comex_operation_product_line
            WHERE id IN (
                SELECT id
                FROM (
                    SELECT
                        id,
                        ROW_NUMBER() OVER (PARTITION BY {column} ORDER BY id) AS position
                    FROM comex_operation_product_line
                    WHERE {column} IS NOT NULL
                ) ranked
                WHERE ranked.position > 1
            )
        """.format(column=column))
        if cr.rowcount:
            _logger.warning(
                "COMEX migration: removed %s duplicated product lines on %s.",
                cr.rowcount, column,
            )

    cr.execute("""
        SELECT COUNT(*)
        FROM comex_operation operation
        WHERE NOT EXISTS (
            SELECT 1
            FROM comex_operation_product_line line
            WHERE line.operation_id = operation.id
        )
    """)
    _logger.info(
        "COMEX migration: %s operations have no product line and will appear as a "
        "single row in the line analysis.",
        cr.fetchone()[0],
    )
