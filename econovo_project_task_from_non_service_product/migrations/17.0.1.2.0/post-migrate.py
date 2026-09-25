# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import SUPERUSER_ID
from odoo.api import Environment


def migrate(cr, version):
    """Re-open invoicing on zero-priced lines that generated a Field Service task.

    ``industry_fsm_sale`` had already stored ``qty_to_invoice = 0`` on them, and
    that guard is now skipped for this kind of line. Stored computed fields are
    not re-evaluated by an upgrade on their own, so force it once here.
    """
    env = Environment(cr, SUPERUSER_ID, {})
    lines = env['sale.order.line'].search([
        ('task_id.is_fsm', '=', True),
        ('state', '=', 'sale'),
    ])._get_fsm_warranty_service_lines()
    if not lines:
        return
    lines._compute_qty_to_invoice()
    lines._compute_invoice_status()
    lines.flush_recordset(['qty_to_invoice', 'invoice_status'])
