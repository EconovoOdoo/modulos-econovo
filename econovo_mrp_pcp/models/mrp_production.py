# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class MrpProduction(models.Model):
    _inherit = 'mrp.production'

    # Tighten the existing plan_id (added by gg_automatic_mrp_schedule) to the
    # standard multi-company safety check now that mrp.plan has a company_id.
    plan_id = fields.Many2one(check_company=True)
    reason_id = fields.Many2one('pcp.reason', string='Manufacturing Reason')
    plan_priority_id = fields.Many2one(
        related='plan_id.priority_id', store=True, string='Plan Priority')
    plan_active = fields.Boolean(
        related='plan_id.active', store=True, string='Plan Active')
