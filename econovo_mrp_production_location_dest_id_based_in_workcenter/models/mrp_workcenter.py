# -*- coding: utf-8 -*-

from odoo import fields, models, api


class MrpWorkcenter(models.Model):
    _inherit = 'mrp.workcenter'

    location_dest_id = fields.Many2one(
        'stock.location', 
        string='Destination Location',
        domain="[('usage', '=', 'internal'), ('company_id', 'in', [company_id, False])]",
        check_company=True,
        help="Location where finished products from this work center should be stored. "
             "If not set, the default location from the operation type will be used."
    )

    @api.depends('location_dest_id')
    def _compute_has_custom_destination(self):
        """Compute if workcenter has a custom destination location"""
        for workcenter in self:
            workcenter.has_custom_destination = bool(workcenter.location_dest_id)

    has_custom_destination = fields.Boolean(
        string='Has Custom Destination',
        compute='_compute_has_custom_destination',
        store=True,
        help="Technical field indicating if this workcenter has a custom destination location"
    )
