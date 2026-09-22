# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

BULK_GROUP = 'econovo_mrp_subcontracting_wizard.group_subcontracting_operation_manager'


class MrpSubcontractingBulk(models.TransientModel):
    _name = 'mrp.subcontracting.bulk'
    _description = 'Bulk Externalization and Internalization'

    mode = fields.Selection(
        [('externalize', 'Externalize an operation'),
         ('internalize', 'Internalize an operation')],
        default='externalize', required=True,
    )
    state = fields.Selection(
        [('setup', 'Setup'), ('running', 'Running'), ('done', 'Finished')],
        default='setup', required=True,
    )
    company_id = fields.Many2one(
        'res.company', required=True, default=lambda self: self.env.company,
    )
    operation_category_id = fields.Many2one(
        'mrp.routing.operation.category', string='Operation Category', required=True,
        help='Every Bill of Materials having an operation of this category is selected.',
    )
    subcontractor_id = fields.Many2one(
        'res.partner', string='Subcontractor', domain="[('is_company', '=', True)]",
    )
    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Warehouse', check_company=True,
    )
    seller_price = fields.Float(string='Subcontracting Price')
    add_mto_route = fields.Boolean(string='Replenish on Order (MTO)')
    chunk_size = fields.Integer(
        string='Records per Run', default=25, required=True,
        help='How many records are processed each time you press Process. Keep it low enough '
             'to stay well below the server request timeout.',
    )
    line_ids = fields.One2many('mrp.subcontracting.bulk.line', 'wizard_id', string='Records')
    total_count = fields.Integer(compute='_compute_progress')
    pending_count = fields.Integer(compute='_compute_progress')
    done_count = fields.Integer(compute='_compute_progress')
    error_count = fields.Integer(compute='_compute_progress')
    progress = fields.Float(compute='_compute_progress', string='Progress (%)')

    @api.depends('line_ids.state')
    def _compute_progress(self):
        for wizard in self:
            lines = wizard.line_ids
            wizard.total_count = len(lines)
            wizard.pending_count = len(lines.filtered(lambda l: l.state == 'pending'))
            wizard.done_count = len(lines.filtered(lambda l: l.state == 'done'))
            wizard.error_count = len(lines.filtered(lambda l: l.state == 'error'))
            processed = wizard.total_count - wizard.pending_count
            wizard.progress = (processed / wizard.total_count * 100) if wizard.total_count else 0.0

    @api.onchange('company_id')
    def _onchange_company_id(self):
        self.warehouse_id = self.env['stock.warehouse'].search(
            [('company_id', '=', self.company_id.id)], limit=1)

    def action_load(self):
        """Select the records matching the criteria without changing anything yet."""
        self.ensure_one()
        self._check_bulk_allowed()
        if self.mode == 'externalize':
            if not self.subcontractor_id or not self.warehouse_id:
                raise UserError(_('Pick a subcontractor and a warehouse first.'))
            operations = self.env['mrp.routing.workcenter'].search([
                ('operation_category_id', '=', self.operation_category_id.id),
                ('bom_id.type', '=', 'normal'),
                ('bom_id.company_id', '=', self.company_id.id),
                ('bom_id.subcontracting_chain_id', '=', False),
            ])
            values = [
                (0, 0, {'bom_id': operation.bom_id.id, 'operation_id': operation.id})
                for operation in operations
            ]
        else:
            chains = self.env['mrp.subcontracting.chain'].search([
                ('operation_category_id', '=', self.operation_category_id.id),
                ('company_id', '=', self.company_id.id),
                ('state', '=', 'externalized'),
            ])
            values = [(0, 0, {'chain_id': chain.id}) for chain in chains]
        if not values:
            raise UserError(_('No record matches these criteria.'))
        self.line_ids = [(5, 0, 0)] + values
        self.state = 'running'
        return self._reopen()

    def action_process_chunk(self):
        """Process the next chunk. Each run is its own transaction, so progress is kept."""
        self.ensure_one()
        self._check_bulk_allowed()
        pending = self.line_ids.filtered(lambda line: line.state == 'pending')
        for line in pending[:self.chunk_size]:
            line._process()
        if not self.line_ids.filtered(lambda line: line.state == 'pending'):
            self.state = 'done'
        return self._reopen()

    def action_retry_errors(self):
        self.ensure_one()
        self.line_ids.filtered(lambda line: line.state == 'error').write({
            'state': 'pending',
            'error_message': False,
        })
        self.state = 'running'
        return self._reopen()

    def _check_bulk_allowed(self):
        """Bulk mode applies structural changes without an ECO, so it is group restricted."""
        self.ensure_one()
        if not self.env.user.has_group(BULK_GROUP):
            raise UserError(_(
                'Bulk mode applies Bill of Materials changes directly, without an Engineering '
                'Change Order. Only members of "Operation Subcontracting / Manager" can run it.'
            ))

    def _reopen(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class MrpSubcontractingBulkLine(models.TransientModel):
    _name = 'mrp.subcontracting.bulk.line'
    _description = 'Bulk Subcontracting Record'

    wizard_id = fields.Many2one(
        'mrp.subcontracting.bulk', required=True, ondelete='cascade', index=True,
    )
    bom_id = fields.Many2one('mrp.bom', string='Bill of Materials')
    operation_id = fields.Many2one('mrp.routing.workcenter', string='Operation')
    chain_id = fields.Many2one('mrp.subcontracting.chain', string='Subcontracting Chain')
    state = fields.Selection(
        [('pending', 'Pending'), ('done', 'Done'), ('error', 'Error')],
        default='pending', required=True,
    )
    error_message = fields.Char(readonly=True)

    def _process(self):
        """Run one record, isolating its failure so the rest of the chunk still goes through."""
        for line in self:
            try:
                with line.env.cr.savepoint():
                    line._apply()
            except Exception as error:  # noqa: BLE001 - reported per record, never aborts the run
                _logger.warning('Bulk subcontracting failed for line %s: %s', line.id, error)
                line.write({'state': 'error', 'error_message': str(error)[:500]})
            else:
                line.write({'state': 'done', 'error_message': False})

    def _apply(self):
        """Apply the change with an explicitly scoped sudo.

        Bulk mode does not create an ECO, so it has to write on Bills of Materials that the
        PLM guard locks. Authorization was already checked against the module group by the
        wizard; the elevation is limited to the structural writes performed by the engine.
        """
        self.ensure_one()
        wizard = self.wizard_id
        Chain = self.env['mrp.subcontracting.chain'].sudo()
        if wizard.mode == 'externalize':
            Chain._externalize(
                self.bom_id.sudo(),
                self.operation_id.sudo(),
                wizard.subcontractor_id,
                wizard.warehouse_id,
                seller_price=wizard.seller_price,
                add_mto_route=wizard.add_mto_route,
                activate=True,
            ).write({'applied_without_eco': True})
        else:
            workcenter = self.chain_id.original_workcenter_id
            if not workcenter or not workcenter.active:
                raise UserError(_(
                    'The original work center of chain %s is missing or archived, so this '
                    'record needs the individual assistant.', self.chain_id.display_name))
            self.chain_id.sudo()._internalize(workcenter, activate=True)
            self.chain_id.sudo().applied_without_eco = True
