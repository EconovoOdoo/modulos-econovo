# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class StockQuantPutawayMultiLine(models.TransientModel):
    _name = 'stock.quant.putaway.multi.line'
    _description = 'Stock Quant Putaway Multi Line'

    wizard_id = fields.Many2one(
        comodel_name='stock.quant.putaway.multi',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    quant_id = fields.Many2one(
        comodel_name='stock.quant',
        string='Quant',
        required=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Product',
        related='quant_id.product_id',
        readonly=True,
    )
    current_location_id = fields.Many2one(
        comodel_name='stock.location',
        string='Current Location',
        related='quant_id.location_id',
        readonly=True,
    )
    quantity = fields.Float(
        string='Quantity',
        related='quant_id.quantity',
        readonly=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        related='quant_id.company_id',
        readonly=True,
    )
    
    # Rule configuration per line
    location_out_id = fields.Many2one(
        comodel_name='stock.location',
        string='Store To',
        domain="[('usage', '=', 'internal'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        compute='_compute_location_out_id',
        store=True,
        readonly=False,
        help='The destination location for this product putaway rule.',
    )
    has_existing_rule = fields.Boolean(
        string='Has Existing Rule',
        compute='_compute_has_existing_rule',
    )
    existing_rule_count = fields.Integer(
        string='Existing Rules Count',
        compute='_compute_has_existing_rule',
    )
    selected = fields.Boolean(
        string='Create Rule',
        default=True,
        help='If checked, a putaway rule will be created for this quant.',
    )

    @api.depends('quant_id.location_id', 'wizard_id.use_current_location')
    def _compute_location_out_id(self):
        for line in self:
            if line.wizard_id.use_current_location:
                line.location_out_id = line.current_location_id
            elif not line.location_out_id:
                line.location_out_id = line.current_location_id

    @api.depends('product_id', 'company_id', 'wizard_id.location_in_id')
    def _compute_has_existing_rule(self):
        for line in self:
            rules = self.env['stock.putaway.rule'].search([
                ('product_id', '=', line.product_id.id),
                ('location_in_id', '=', line.wizard_id.location_in_id.id),
                ('company_id', '=', line.company_id.id),
            ])
            line.has_existing_rule = bool(rules)
            line.existing_rule_count = len(rules)
