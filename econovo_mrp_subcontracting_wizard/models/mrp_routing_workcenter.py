# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
from odoo import _, fields, models
from odoo.exceptions import UserError


class MrpRoutingWorkcenter(models.Model):
    _inherit = 'mrp.routing.workcenter'

    operation_category_id = fields.Many2one(
        'mrp.routing.operation.category',
        string='Operation Category',
        help='Determines the suffix of the intermediate products generated when this '
             'operation is externalized to a subcontractor.',
    )

    def action_externalize_operation(self):
        """Open the externalization assistant for the selected operation(s)."""
        if not self:
            raise UserError(_('Select at least one operation to externalize.'))
        orphans = self.filtered(lambda operation: not operation.bom_id)
        if orphans:
            raise UserError(_('An operation can only be externalized from a Bill of Materials.'))
        busy = self.filtered(
            lambda operation:
            operation.bom_id.subcontracting_chain_id.state == 'externalized')
        if busy:
            raise UserError(_(
                'These Bills of Materials are already subcontracted, internalize them first:\n%s',
                '\n'.join('- %s' % name for name in busy.bom_id.mapped('display_name')),
            ))
        if len(self) == 1:
            return {
                'name': _('Externalize an Operation'),
                'type': 'ir.actions.act_window',
                'res_model': 'mrp.subcontracting.externalization',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_bom_id': self.bom_id.id,
                    'default_operation_id': self.id,
                },
            }
        company = self._get_common_company()
        wizard = self.env['mrp.subcontracting.bulk'].create({
            'mode': 'externalize',
            'company_id': company.id,
            'line_ids': [
                (0, 0, {'bom_id': operation.bom_id.id, 'operation_id': operation.id})
                for operation in self
            ],
        })
        return wizard._reopen()

    def action_internalize_operation(self):
        """Open the internalization assistant for the chains the selection belongs to."""
        chains = self.bom_id.subcontracting_chain_id.filtered(
            lambda chain: chain.state == 'externalized')
        if not chains:
            raise UserError(_(
                'None of the selected operations belongs to a Bill of Materials that is '
                'currently subcontracted.'))
        if len(chains) == 1:
            return chains.action_open_internalization_wizard()
        wizard = self.env['mrp.subcontracting.bulk'].create({
            'mode': 'internalize',
            'company_id': self._get_common_company().id,
            'line_ids': [(0, 0, {'chain_id': chain.id}) for chain in chains],
        })
        return wizard._reopen()

    def _get_common_company(self):
        """Return the single company of the selection, refusing a mixed one."""
        companies = self.bom_id.company_id
        if len(companies) > 1:
            raise UserError(_('Select operations belonging to a single company.'))
        return companies or self.env.company
