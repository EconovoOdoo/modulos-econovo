# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class StockPickingBatch(models.Model):
    _inherit = 'stock.picking.batch'

    production_plan_id = fields.Many2one(
        'mrp.plan', string='Production Plan',
        compute='_compute_production_plan_id', store=True,
        help="Production Plan shared by the transfers in this batch. It is "
             "empty when the batch contains transfers from different plans.")

    @api.depends('picking_ids.production_plan_id')
    def _compute_production_plan_id(self):
        for batch in self:
            pickings = batch.picking_ids
            planned_pickings = pickings.filtered('production_plan_id')
            plans = planned_pickings.mapped('production_plan_id')
            batch.production_plan_id = (
                plans if len(plans) == 1 and len(planned_pickings) == len(pickings)
                else False
            )