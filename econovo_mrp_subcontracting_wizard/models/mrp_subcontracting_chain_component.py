# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
from odoo import api, fields, models


class MrpSubcontractingChainComponent(models.Model):
    _name = 'mrp.subcontracting.chain.component'
    _description = 'Subcontracting Chain Component'
    _order = 'product_tmpl_id'

    chain_id = fields.Many2one(
        'mrp.subcontracting.chain', required=True, ondelete='cascade', index=True,
    )
    product_tmpl_id = fields.Many2one(
        'product.template', string='Component', required=True,
    )
    has_resupply_route = fields.Boolean(
        string='Resupply Route Set', compute='_compute_has_resupply_route',
        help='Without this route Odoo never generates the delivery of this component to the '
             'subcontractor, and it fails silently.',
    )
    state = fields.Selection(
        [('ok', 'Ready'), ('warning', 'Missing Route')],
        compute='_compute_has_resupply_route',
    )

    @api.depends('product_tmpl_id.route_ids', 'chain_id.warehouse_id')
    def _compute_has_resupply_route(self):
        for line in self:
            route = line.chain_id.warehouse_id.subcontracting_route_id
            line.has_resupply_route = bool(route) and route in line.product_tmpl_id.route_ids
            line.state = 'ok' if line.has_resupply_route else 'warning'
