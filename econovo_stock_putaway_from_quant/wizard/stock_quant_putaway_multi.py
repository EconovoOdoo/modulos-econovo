from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockQuantPutawayMulti(models.TransientModel):
    _name = 'stock.quant.putaway.multi'
    _description = 'Stock Quant Putaway Multi Wizard'

    quant_ids = fields.Many2many(
        comodel_name='stock.quant',
        string='Quants',
        readonly=True,
    )
    line_ids = fields.One2many(
        comodel_name='stock.quant.putaway.multi.line',
        inverse_name='wizard_id',
        string='Lines',
        compute='_compute_line_ids',
        store=True,
        readonly=False,
    )
    quant_count = fields.Integer(
        string='Quant Count',
        compute='_compute_quant_count',
    )
    selected_count = fields.Integer(
        string='Selected Count',
        compute='_compute_selected_count',
    )
    
    # Common configuration
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        compute='_compute_company_id',
        help='Company from the first quant. Used for domain filtering.',
    )
    location_in_id = fields.Many2one(
        comodel_name='stock.location',
        string='When Product Arrives In',
        domain="[('usage', '=', 'internal'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help='The parent location where products arrive. '
             'Usually the main stock location of the warehouse.',
    )
    use_current_location = fields.Boolean(
        string='Use Current Location as Destination',
        default=True,
        help='If checked, each product will use its current quant location '
             'as the destination for the putaway rule.',
    )
    sequence = fields.Integer(
        string='Priority',
        default=1,
        help='Lower values have higher priority.',
    )
    replace_existing = fields.Boolean(
        string='Replace Existing Rules',
        default=False,
        help='If checked, existing putaway rules for products '
             'in the selected source location will be deactivated.',
    )
    skip_existing = fields.Boolean(
        string='Skip Products with Existing Rules',
        default=False,
        help='If checked, products that already have a putaway rule '
             'for the source location will be skipped.',
    )
    has_conflicts = fields.Boolean(
        string='Has Conflicts',
        compute='_compute_has_conflicts',
    )

    @api.depends('quant_ids')
    def _compute_company_id(self):
        """Get company from first quant for domain filtering."""
        for wizard in self:
            if wizard.quant_ids:
                wizard.company_id = wizard.quant_ids[0].company_id
            else:
                wizard.company_id = self.env.company

    @api.depends('quant_ids')
    def _compute_quant_count(self):
        for wizard in self:
            wizard.quant_count = len(wizard.quant_ids)

    @api.depends('line_ids.selected')
    def _compute_selected_count(self):
        for wizard in self:
            wizard.selected_count = len(wizard.line_ids.filtered('selected'))

    @api.depends('quant_ids')
    def _compute_line_ids(self):
        for wizard in self:
            lines_vals = []
            for quant in wizard.quant_ids:
                lines_vals.append({
                    'wizard_id': wizard.id,
                    'quant_id': quant.id,
                    'location_out_id': quant.location_id.id,
                    'selected': True,
                })
            wizard.line_ids = [(5, 0, 0)] + [(0, 0, vals) for vals in lines_vals]

    @api.depends('line_ids.has_existing_rule')
    def _compute_has_conflicts(self):
        for wizard in self:
            wizard.has_conflicts = any(
                line.has_existing_rule for line in wizard.line_ids.filtered('selected')
            )

    @api.onchange('use_current_location')
    def _onchange_use_current_location(self):
        if self.use_current_location:
            for line in self.line_ids:
                line.location_out_id = line.current_location_id

    def action_create_rules(self):
        """Create putaway rules for all selected lines."""
        self.ensure_one()

        if not self.location_in_id:
            raise UserError(_('Please select a source location.'))

        selected_lines = self.line_ids.filtered('selected')
        if not selected_lines:
            raise UserError(_('Please select at least one product.'))

        created_count = 0
        skipped_count = 0
        replaced_count = 0

        for line in selected_lines:
            location_out = line.location_out_id
            if not location_out:
                raise UserError(_(
                    'Please select a destination location for product "%(product)s".',
                    product=line.product_id.display_name,
                ))

            # Check for existing rules
            existing_rules = self.env['stock.putaway.rule'].search([
                ('product_id', '=', line.product_id.id),
                ('location_in_id', '=', self.location_in_id.id),
                ('company_id', '=', line.company_id.id),
            ])

            if existing_rules:
                if self.skip_existing:
                    skipped_count += 1
                    continue
                elif self.replace_existing:
                    existing_rules.write({'active': False})
                    replaced_count += len(existing_rules)

            # Check if exact rule already exists
            exact_rule = self.env['stock.putaway.rule'].search([
                ('product_id', '=', line.product_id.id),
                ('location_in_id', '=', self.location_in_id.id),
                ('location_out_id', '=', location_out.id),
                ('company_id', '=', line.company_id.id),
            ], limit=1)

            if exact_rule:
                skipped_count += 1
                continue

            # Create the new putaway rule
            self.env['stock.putaway.rule'].create({
                'product_id': line.product_id.id,
                'location_in_id': self.location_in_id.id,
                'location_out_id': location_out.id,
                'sequence': self.sequence,
                'company_id': line.company_id.id,
            })
            created_count += 1

        # Show result message
        message = _('Created %(created)s putaway rule(s).', created=created_count)
        if skipped_count:
            message += ' ' + _('Skipped %(skipped)s (already exist).', skipped=skipped_count)
        if replaced_count:
            message += ' ' + _('Replaced %(replaced)s existing rule(s).', replaced=replaced_count)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Putaway Rules Created'),
                'message': message,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_select_all(self):
        """Select all lines."""
        self.line_ids.write({'selected': True})
        return {'type': 'ir.actions.act_window_close'}

    def action_deselect_all(self):
        """Deselect all lines."""
        self.line_ids.write({'selected': False})
        return {'type': 'ir.actions.act_window_close'}
