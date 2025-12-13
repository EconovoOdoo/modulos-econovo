from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockMoveLinePutaway(models.TransientModel):
    _name = 'stock.move.line.putaway'
    _description = 'Stock Move Line Putaway Wizard'

    # Reference to the picking
    picking_id = fields.Many2one(
        comodel_name='stock.picking',
        string='Picking',
        readonly=True,
    )
    picking_name = fields.Char(
        string='Picking Reference',
        related='picking_id.name',
        readonly=True,
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Partner',
        related='picking_id.partner_id',
        readonly=True,
    )

    # Wizard lines
    line_ids = fields.One2many(
        comodel_name='stock.move.line.putaway.line',
        inverse_name='wizard_id',
        string='Lines',
    )
    line_count = fields.Integer(
        string='Line Count',
        compute='_compute_line_count',
    )
    selected_count = fields.Integer(
        string='Selected Count',
        compute='_compute_selected_count',
    )
    has_existing_rules = fields.Boolean(
        string='Has Existing Rules',
        compute='_compute_has_existing_rules',
    )

    # Configuration
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
    )
    location_in_id = fields.Many2one(
        comodel_name='stock.location',
        string='When Product Arrives In',
        domain="[('usage', '=', 'internal'), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        required=True,
        help='The parent location where products arrive (from the picking destination).',
    )
    sequence = fields.Integer(
        string='Priority',
        default=1,
        help='Lower values have higher priority.',
    )

    # Options
    skip_existing = fields.Boolean(
        string='Skip Products with Existing Rules',
        default=True,
        help='If checked, products that already have a putaway rule for the '
             'source location will be skipped.',
    )
    replace_existing = fields.Boolean(
        string='Replace Existing Rules',
        default=False,
        help='If checked, existing putaway rules for the same product and '
             'source location will be deactivated and replaced with the new rule.',
    )

    @api.depends('line_ids')
    def _compute_line_count(self):
        for wizard in self:
            wizard.line_count = len(wizard.line_ids)

    @api.depends('line_ids.selected')
    def _compute_selected_count(self):
        for wizard in self:
            wizard.selected_count = len(wizard.line_ids.filtered('selected'))

    @api.depends('line_ids.has_existing_rule')
    def _compute_has_existing_rules(self):
        for wizard in self:
            wizard.has_existing_rules = any(wizard.line_ids.mapped('has_existing_rule'))

    @api.onchange('skip_existing')
    def _onchange_skip_existing(self):
        """Mutually exclusive with replace_existing."""
        if self.skip_existing:
            self.replace_existing = False

    @api.onchange('replace_existing')
    def _onchange_replace_existing(self):
        """Mutually exclusive with skip_existing."""
        if self.replace_existing:
            self.skip_existing = False

    def action_create_rules(self):
        """Create putaway rules for selected lines."""
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
            if not line.product_id:
                continue

            location_out = line.location_out_id
            if not location_out:
                skipped_count += 1
                continue

            # Check for existing rule
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
                else:
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

        # Show result message and close modal
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
                'next': {'type': 'ir.actions.act_window_close'},
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
