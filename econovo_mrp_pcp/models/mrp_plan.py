# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class MrpPlan(models.Model):
    _inherit = 'mrp.plan'

    active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company)
    priority_id = fields.Many2one('pcp.priority', string='Priority')
    date_start = fields.Date(string='Target Start Date')
    date_end = fields.Date(string='Target End Date')
