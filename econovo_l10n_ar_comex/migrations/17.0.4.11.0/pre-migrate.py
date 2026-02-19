# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Merge M2M data from old auto-generated table into canonical table.

    account.move.comex_operation_ids previously used an auto-generated
    relation table (account_move_comex_operation_rel) instead of the
    explicit table used by comex.operation.invoice_ids
    (comex_operation_invoice_rel). This migration copies any rows from
    the old table into the canonical one before the ORM switches.
    """
    # Check if the old auto-generated table exists
    cr.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'account_move_comex_operation_rel'
        )
    """)
    if not cr.fetchone()[0]:
        _logger.info(
            "COMEX migration: old table account_move_comex_operation_rel "
            "does not exist, nothing to migrate."
        )
        return

    # Ensure the canonical table exists
    cr.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'comex_operation_invoice_rel'
        )
    """)
    if not cr.fetchone()[0]:
        _logger.info(
            "COMEX migration: canonical table comex_operation_invoice_rel "
            "does not exist yet, skipping (ORM will create it)."
        )
        return

    # Copy rows from old table, ignoring duplicates
    cr.execute("""
        INSERT INTO comex_operation_invoice_rel (operation_id, invoice_id)
        SELECT comex_operation_id, account_move_id
        FROM account_move_comex_operation_rel
        ON CONFLICT DO NOTHING
    """)
    migrated = cr.rowcount
    _logger.info(
        "COMEX migration: merged %d rows from "
        "account_move_comex_operation_rel into "
        "comex_operation_invoice_rel.", migrated
    )
