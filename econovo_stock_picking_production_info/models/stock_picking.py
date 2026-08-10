# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    workcenter_id = fields.Many2one(
        'mrp.workcenter', string='Workcenter',
        related='group_id.mrp_production_ids.workorder_ids.workcenter_id', store=True,
        help="Workcenter of the Manufacturing Order sharing this transfer's "
             "procurement group.")
    production_plan_id = fields.Many2one(
        'mrp.plan', string='Production Plan',
        related='group_id.mrp_production_ids.plan_id', store=True,
        help="Production Plan of the Manufacturing Order sharing this "
             "transfer's procurement group (e.g. the MO a 'Choose "
             "Components' transfer supplies).")



