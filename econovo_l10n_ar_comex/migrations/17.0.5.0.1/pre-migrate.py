# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

import logging

_logger = logging.getLogger(__name__)

ACTION_XMLID = 'comex_operation_product_line_action'
MENU_XMLID = 'menu_comex_operation_product_lines'


def migrate(cr, version):
    """Let the COMEX line analysis action be updated again by the module.

    The action was edited outside the repository (Odoo Studio flags every record
    it touches), which set noupdate on its ir.model.data row. As a result the
    17.0.5.0.0 upgrade installed the new analysis model and its views but kept
    the action pointing at the raw product line model.
    """
    cr.execute("""
        UPDATE ir_model_data
           SET noupdate = FALSE
         WHERE module = 'econovo_l10n_ar_comex'
           AND name = %s
           AND noupdate
    """, (ACTION_XMLID,))
    if cr.rowcount:
        _logger.warning(
            "COMEX migration: cleared the noupdate flag of %s so the module can "
            "update it again.", ACTION_XMLID,
        )

    # Stale translations would keep showing the former label in the UI.
    _drop_translations(cr, ACTION_XMLID, 'ir_act_window', ('name', 'help'))
    _drop_translations(cr, MENU_XMLID, 'ir_ui_menu', ('name',))


def _drop_translations(cr, xmlid, table, columns):
    """Keep only the en_US value so the new source terms are shown/retranslated."""
    cr.execute("""
        SELECT res_id
          FROM ir_model_data
         WHERE module = 'econovo_l10n_ar_comex'
           AND name = %s
    """, (xmlid,))
    row = cr.fetchone()
    if not row:
        return

    for column in columns:
        cr.execute("""
            UPDATE {table}
               SET {column} = jsonb_build_object('en_US', {column} ->> 'en_US')
             WHERE id = %s
               AND {column} ? 'en_US'
        """.format(table=table, column=column), (row[0],))
