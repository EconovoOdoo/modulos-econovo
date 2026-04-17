# -*- coding: utf-8 -*-
"""
Migration 17.0.1.1.0 — econovo_fsm_worksheet

Creates the new auto-populated worksheet fields (x_so_name, x_so_oc_cliente,
x_so_factura, x_so_remito) and updates the worksheet form view to use
select dropdowns instead of radio buttons for Tipo de Servicio / Tipo de Falla.

The setup_svt04_worksheet function is idempotent: it skips fields that already
exist and always rewrites the form/search view arch.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    from odoo import api, registry as odoo_registry
    from odoo.addons.econovo_fsm_worksheet.hooks import setup_svt04_worksheet

    with odoo_registry(cr.dbname).cursor() as new_cr:
        env = api.Environment(new_cr, 1, {})
        _logger.info('econovo_fsm_worksheet 17.0.1.1.0: running post-migrate setup.')
        setup_svt04_worksheet(env)
        _logger.info('econovo_fsm_worksheet 17.0.1.1.0: migration complete.')
