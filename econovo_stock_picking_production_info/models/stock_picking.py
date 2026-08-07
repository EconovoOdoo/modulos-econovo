# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    workcenter_id = fields.Many2one('mrp.workcenter', string='Workcenter')
    production_plan_id = fields.Many2one(
        'mrp.plan', string='Production Plan',
        compute='_compute_production_plan_id', store=True,
        help="Production Plan of the Manufacturing Order this transfer "
             "supplies components for.")

    @api.depends('move_ids.raw_material_production_id.plan_id',
                 'move_ids.move_dest_ids.raw_material_production_id.plan_id')
    def _compute_production_plan_id(self):
        for picking in self:
            picking.production_plan_id = picking.move_ids._get_supply_production().plan_id[:1]

