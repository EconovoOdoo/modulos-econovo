from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockQuantPutawaySingle(models.TransientModel):
    _name = 'stock.quant.putaway.single'
    _description = 'Stock Quant Putaway Single Wizard'

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
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        related='quant_id.company_id',
        readonly=True,
    )
    quantity = fields.Float(
        string='Quantity',
        related='quant_id.quantity',
        readonly=True,
    )

    # Existing rules
    existing_rule_ids = fields.One2many(
        comodel_name='stock.quant.putaway.single.line',
        inverse_name='wizard_id',
        string='Existing Putaway Rules',
    )
    has_existing_rules = fields.Boolean(
        string='Has Existing Rules',
        readonly=True,
    )
    has_rule_for_current_location = fields.Boolean(
        string='Has Rule for Current Location',
        readonly=True,
    )

    # New rule fields
    location_in_id = fields.Many2one(
        comodel_name='stock.location',
        string='When Product Arrives In',
        domain="[('usage', '=', 'internal'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help='The parent location where the product arrives. '
             'Usually the main stock location of the warehouse.',
    )
    location_out_id = fields.Many2one(
        comodel_name='stock.location',
        string='Store To',
        domain="[('usage', '=', 'internal'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help='The destination location where the product should be stored.',
    )
    use_current_location = fields.Boolean(
        string='Use Current Location as Destination',
        default=True,
        help='If checked, the current location of the quant will be used '
             'as the destination location for the new rule.',
    )
    sequence = fields.Integer(
        string='Priority',
        default=1,
        help='Lower values have higher priority.',
    )
    replace_existing = fields.Boolean(
        string='Replace Existing Rules',
        default=False,
        help='If checked, existing putaway rules for this product '
             'in the selected source location will be deactivated.',
    )

    @api.model
    def default_get(self, fields_list):
        """Standard Odoo pattern: populate One2many lines in default_get."""
        res = super().default_get(fields_list)
        
        # Get quant from context
        quant_id = self.env.context.get('default_quant_id')
        if not quant_id:
            return res
        
        quant = self.env['stock.quant'].browse(quant_id)
        if not quant.exists():
            return res
        
        # Search existing putaway rules for this product/company
        rules = self.env['stock.putaway.rule'].search([
            ('product_id', '=', quant.product_id.id),
            ('company_id', '=', quant.company_id.id),
        ])
        
        # Set boolean flags
        res['has_existing_rules'] = bool(rules)
        res['has_rule_for_current_location'] = any(
            rule.location_out_id == quant.location_id for rule in rules
        )
        
        if rules and 'existing_rule_ids' in fields_list:
            lines_vals = []
            for rule in rules:
                lines_vals.append((0, 0, {
                    'putaway_rule_id': rule.id,
                    'product_id': rule.product_id.id,
                    'location_in_id': rule.location_in_id.id,
                    'location_out_id': rule.location_out_id.id,
                    'sequence': rule.sequence,
                }))
            res['existing_rule_ids'] = lines_vals
        
        return res

    @api.onchange('use_current_location')
    def _onchange_use_current_location(self):
        if self.use_current_location:
            self.location_out_id = self.current_location_id

    def action_create_rule(self):
        """Create a new putaway rule based on wizard configuration."""
        self.ensure_one()

        # Determine destination location
        if self.use_current_location:
            location_out = self.current_location_id
        else:
            location_out = self.location_out_id

        if not location_out:
            raise UserError(_('Please select a destination location.'))

        if not self.location_in_id:
            raise UserError(_('Please select a source location.'))

        # Check if rule already exists for this combination
        existing_rule = self.env['stock.putaway.rule'].search([
            ('product_id', '=', self.product_id.id),
            ('location_in_id', '=', self.location_in_id.id),
            ('location_out_id', '=', location_out.id),
            ('company_id', '=', self.company_id.id),
        ], limit=1)

        if existing_rule:
            raise UserError(_(
                'A putaway rule already exists for product "%(product)s" '
                'from location "%(location_in)s" to "%(location_out)s".',
                product=self.product_id.display_name,
                location_in=self.location_in_id.display_name,
                location_out=location_out.display_name,
            ))

        # Deactivate existing rules if requested
        if self.replace_existing:
            existing_rules = self.env['stock.putaway.rule'].search([
                ('product_id', '=', self.product_id.id),
                ('location_in_id', '=', self.location_in_id.id),
                ('company_id', '=', self.company_id.id),
            ])
            existing_rules.write({'active': False})

        # Create the new putaway rule
        self.env['stock.putaway.rule'].create({
            'product_id': self.product_id.id,
            'location_in_id': self.location_in_id.id,
            'location_out_id': location_out.id,
            'sequence': self.sequence,
            'company_id': self.company_id.id,
        })

        return {'type': 'ir.actions.act_window_close'}

    def action_view_existing_rules(self):
        """Open the putaway rules view filtered for this product."""
        self.ensure_one()
        return {
            'name': _('Putaway Rules for %s', self.product_id.display_name),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.putaway.rule',
            'view_mode': 'tree,form',
            'domain': [
                ('product_id', '=', self.product_id.id),
                ('company_id', '=', self.company_id.id),
            ],
            'context': {
                'default_product_id': self.product_id.id,
                'default_company_id': self.company_id.id,
            },
        }
