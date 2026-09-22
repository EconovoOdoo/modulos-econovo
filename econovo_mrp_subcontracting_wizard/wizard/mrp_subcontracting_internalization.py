# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MrpSubcontractingInternalization(models.TransientModel):
    _name = 'mrp.subcontracting.internalization'
    _description = 'Internalize a Subcontracted Operation'

    state = fields.Selection(
        [('setup', 'Setup'), ('review', 'Review')], default='setup', required=True,
    )
    chain_id = fields.Many2one(
        'mrp.subcontracting.chain', string='Subcontracting Chain', required=True,
    )
    company_id = fields.Many2one(related='chain_id.company_id')
    workcenter_id = fields.Many2one(
        'mrp.workcenter', string='Work Center', required=True, check_company=True,
        help='Where the operation will be performed again in-house.',
    )
    eco_type_id = fields.Many2one(
        'mrp.eco.type', string='ECO Type', required=True,
        help='Type of Engineering Change Order created to register this change.',
    )
    eco_handling = fields.Selection(
        [
            ('validated', 'Create the ECO already applied'),
            ('auto', 'Create the ECO and follow the approval circuit'),
        ],
        default='validated', required=True, string='PLM Registration',
    )
    operation_line_ids = fields.One2many(
        'mrp.subcontracting.internalization.operation', 'wizard_id', string='Operations',
    )
    component_line_ids = fields.One2many(
        'mrp.subcontracting.internalization.component', 'wizard_id', string='Components',
    )

    @api.onchange('chain_id')
    def _onchange_chain_id(self):
        workcenter = self.chain_id.original_workcenter_id
        self.workcenter_id = workcenter if workcenter.active else False

    def action_next(self):
        """Build the editable preview of the merged Bill of Materials."""
        self.ensure_one()
        plan = self.chain_id._build_internalization_plan()
        restored_sequence = self.chain_id.original_sequence
        operations = [
            (0, 0, {
                'operation_id': operation.id,
                'sequence': operation.sequence,
                'is_restored': False,
            })
            for operation in plan['operations']
        ]
        operations.append((0, 0, {
            'restored_name': self.chain_id.operation_name,
            'sequence': restored_sequence,
            'is_restored': True,
        }))
        self.operation_line_ids = [(5, 0, 0)] + operations
        self.component_line_ids = [(5, 0, 0)] + [
            (0, 0, {'bom_line_id': line.id}) for line in plan['component_lines']
        ]
        self.state = 'review'
        return self._reopen()

    def action_previous(self):
        self.ensure_one()
        self.state = 'setup'
        return self._reopen()

    def action_confirm(self):
        self.ensure_one()
        if self.chain_id.state != 'externalized':
            raise UserError(_('Only an externalized chain can be internalized.'))
        if self.eco_handling == 'validated' and not self._get_apply_stage():
            raise UserError(_(
                'The ECO type "%s" has no stage allowing changes to be applied. Pick another '
                'type or choose to follow the approval circuit.', self.eco_type_id.display_name))
        final_bom = self.chain_id._get_final_bom()
        eco = self.env['mrp.eco'].create({
            'name': _('Internalize %(operation)s of %(product)s',
                      operation=self.chain_id.operation_name or _('the subcontracted stage'),
                      product=self.chain_id.final_product_tmpl_id.display_name),
            'type_id': self.eco_type_id.id,
            'stage_id': self.env['mrp.eco.stage'].search(
                [('type_ids', 'in', self.eco_type_id.ids)], order='sequence, id', limit=1).id,
            'type': 'bom',
            'product_tmpl_id': self.chain_id.final_product_tmpl_id.id,
            'bom_id': final_bom.id,
            'company_id': self.company_id.id,
            'subcontracting_chain_id': self.chain_id.id,
        })
        eco.action_new_revision()
        self.chain_id._internalize(
            self.workcenter_id,
            target_bom=eco.new_bom_id,
            component_lines=self.component_line_ids.filtered('keep').bom_line_id,
            operation_sequences={
                line.operation_id: line.sequence
                for line in self.operation_line_ids if line.operation_id
            },
            activate=False,
        )
        if self.eco_handling == 'validated':
            eco.stage_id = self._get_apply_stage().id
            eco.action_apply()
            self.chain_id.write({
                'validated_by_id': self.env.user.id,
                'validated_date': fields.Datetime.now(),
            })
            eco.message_post(body=_(
                'Applied automatically by the operation subcontracting assistant, without '
                'going through the manual approval circuit.'))
        return {
            'name': _('Subcontracting Chain'),
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.subcontracting.chain',
            'view_mode': 'form',
            'res_id': self.chain_id.id,
        }

    def _get_apply_stage(self):
        self.ensure_one()
        return self.env['mrp.eco.stage'].search([
            ('allow_apply_change', '=', True),
            ('type_ids', 'in', self.eco_type_id.ids),
        ], order='sequence, id', limit=1)

    def _reopen(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class MrpSubcontractingInternalizationOperation(models.TransientModel):
    _name = 'mrp.subcontracting.internalization.operation'
    _description = 'Operation of the Merged Route'
    _order = 'sequence, id'

    wizard_id = fields.Many2one(
        'mrp.subcontracting.internalization', required=True, ondelete='cascade',
    )
    operation_id = fields.Many2one('mrp.routing.workcenter', string='Existing Operation')
    restored_name = fields.Char(string='Restored Operation')
    is_restored = fields.Boolean(
        string='Back In-House',
        help='The operation that was being performed by the subcontractor.',
    )
    sequence = fields.Integer(required=True)
    display_operation = fields.Char(compute='_compute_display_operation', string='Operation')

    @api.depends('operation_id', 'restored_name')
    def _compute_display_operation(self):
        for line in self:
            line.display_operation = line.operation_id.name or line.restored_name


class MrpSubcontractingInternalizationComponent(models.TransientModel):
    _name = 'mrp.subcontracting.internalization.component'
    _description = 'Component of the Merged Bill of Materials'

    wizard_id = fields.Many2one(
        'mrp.subcontracting.internalization', required=True, ondelete='cascade',
    )
    bom_line_id = fields.Many2one('mrp.bom.line', string='Component Line', required=True)
    product_id = fields.Many2one(related='bom_line_id.product_id', string='Component')
    product_qty = fields.Float(related='bom_line_id.product_qty', string='Quantity')
    source_bom_id = fields.Many2one(related='bom_line_id.bom_id', string='Coming From')
    keep = fields.Boolean(
        string='Keep', default=True,
        help='Uncheck to leave this component out of the merged Bill of Materials.',
    )
