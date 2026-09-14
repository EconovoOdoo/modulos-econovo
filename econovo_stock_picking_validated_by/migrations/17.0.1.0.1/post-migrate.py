# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Backfill ``validation_user_id`` on records that were already
    ``done`` before this module (or this fix) existed.

    Runs in 4 steps:

    1. ``stock.picking``: for done transfers with no value yet, look up
       who authored the most recent "state changed" tracking message
       (``mail.tracking.value``) - that is who actually validated it.
    2. ``stock.move``: copy the transfer's value (from step 1, or
       already set) down to its moves.
    3. ``stock.move``: for done moves with NO transfer at all (inventory
       adjustments, quant relocations - ``stock.quant._apply_inventory()``/
       ``move_quants()`` create and complete the move in the very same
       call), use ``create_uid`` directly.
    4. ``stock.move.line``: copy the move's value down to its lines.
    """
    cr.execute("""
        UPDATE stock_picking sp
        SET validation_user_id = latest.create_uid
        FROM (
            SELECT DISTINCT ON (mm.res_id)
                mm.res_id AS picking_id,
                mm.create_uid AS create_uid
            FROM mail_tracking_value mtv
            JOIN mail_message mm ON mm.id = mtv.mail_message_id
            JOIN ir_model_fields imf ON imf.id = mtv.field_id
            WHERE mm.model = 'stock.picking'
              AND imf.model = 'stock.picking'
              AND imf.name = 'state'
            ORDER BY mm.res_id, mtv.id DESC
        ) latest
        WHERE sp.id = latest.picking_id
          AND sp.state = 'done'
          AND sp.validation_user_id IS NULL
    """)
    _logger.info(
        "econovo_stock_picking_validated_by: backfilled validation_user_id "
        "on %s historical done picking(s) from tracking history",
        cr.rowcount)

    cr.execute("""
        UPDATE stock_move sm
        SET validation_user_id = sp.validation_user_id
        FROM stock_picking sp
        WHERE sm.picking_id = sp.id
          AND sm.state = 'done'
          AND sm.validation_user_id IS NULL
          AND sp.validation_user_id IS NOT NULL
    """)
    _logger.info(
        "econovo_stock_picking_validated_by: backfilled validation_user_id "
        "on %s move(s) from their transfer", cr.rowcount)

    cr.execute("""
        UPDATE stock_move
        SET validation_user_id = create_uid
        WHERE state = 'done'
          AND picking_id IS NULL
          AND validation_user_id IS NULL
          AND create_uid IS NOT NULL
    """)
    _logger.info(
        "econovo_stock_picking_validated_by: backfilled validation_user_id "
        "on %s picking-less move(s) from create_uid", cr.rowcount)

    cr.execute("""
        UPDATE stock_move_line sml
        SET validation_user_id = sm.validation_user_id
        FROM stock_move sm
        WHERE sml.move_id = sm.id
          AND sml.validation_user_id IS NULL
          AND sm.validation_user_id IS NOT NULL
    """)
    _logger.info(
        "econovo_stock_picking_validated_by: backfilled validation_user_id "
        "on %s move line(s) from their move", cr.rowcount)
