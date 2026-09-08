# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class MrpWorkorder(models.Model):
    _inherit = 'mrp.workorder'

    # Own, versioned equivalent of the pre-existing Studio field x_studio_mo_plan_id.
    plan_id = fields.Many2one(
        related='production_id.plan_id', store=True, string='Production Plan')
    plan_priority_id = fields.Many2one(
        related='production_id.plan_id.priority_id', store=True, string='Plan Priority')
    plan_active = fields.Boolean(
        related='production_id.plan_id.active', store=True, string='Plan Active')
