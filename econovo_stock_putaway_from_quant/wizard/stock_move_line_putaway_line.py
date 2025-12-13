from odoo import api, fields, models


class StockMoveLinePutawayLine(models.TransientModel):
    _name = 'stock.move.line.putaway.line'
    _description = 'Stock Move Line Putaway Wizard Line'

    wizard_id = fields.Many2one(
        comodel_name='stock.move.line.putaway',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    move_line_id = fields.Many2one(
        comodel_name='stock.move.line',
        string='Move Line',
        readonly=True,
    )

    # Product info from move line
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Product',
        related='move_line_id.product_id',
        readonly=True,
    )
    product_uom_qty = fields.Float(
        string='Quantity',
        related='move_line_id.quantity',
        readonly=True,
    )
    product_uom_id = fields.Many2one(
        comodel_name='uom.uom',
        string='UoM',
        related='move_line_id.product_uom_id',
        readonly=True,
    )
    lot_id = fields.Many2one(
        comodel_name='stock.lot',
        string='Lot/Serial',
        related='move_line_id.lot_id',
        readonly=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        related='move_line_id.company_id',
        readonly=True,
    )

    # Locations
    location_id = fields.Many2one(
        comodel_name='stock.location',
        string='From',
        related='move_line_id.location_id',
        readonly=True,
    )
    location_out_id = fields.Many2one(
        comodel_name='stock.location',
        string='Store In',
        domain="[('id', 'child_of', parent.location_in_id), ('usage', '=', 'internal')]",
        help='Destination sublocation where the product will be stored.',
    )

    # Selection
    selected = fields.Boolean(
        string='Create Rule',
        default=True,
    )

    # Existing rules
    has_existing_rule = fields.Boolean(
        string='Has Existing Rule',
        compute='_compute_has_existing_rule',
    )
    existing_rules_count = fields.Integer(
        string='Existing Rules',
        compute='_compute_has_existing_rule',
    )

    @api.depends('product_id', 'wizard_id.location_in_id', 'company_id')
    def _compute_has_existing_rule(self):
        for line in self:
            if not line.product_id or not line.wizard_id.location_in_id:
                line.has_existing_rule = False
                line.existing_rules_count = 0
                continue

            rules = self.env['stock.putaway.rule'].search([
                ('product_id', '=', line.product_id.id),
                ('location_in_id', '=', line.wizard_id.location_in_id.id),
                ('company_id', '=', line.company_id.id),
            ])
            line.existing_rules_count = len(rules)
            line.has_existing_rule = bool(rules)
