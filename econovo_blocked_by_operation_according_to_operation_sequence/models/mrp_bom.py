# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    def action_set_operation_dependencies(self):
        """
        Set up operation dependencies based on sequence.
        Each operation will be blocked by the previous operation in the sequence.
        """
        self.ensure_one()
        
        # Check if operation dependencies are allowed
        if not self.allow_operation_dependencies:
            raise UserError(_("Operation dependencies are not enabled for this BoM. Please enable them first."))

        # Get operations sorted by sequence
        operations = self.operation_ids.sorted(key=lambda r: r.sequence)
        
        # Reset all existing blocked_by_operation_ids relationships for these operations
        operations.write({'blocked_by_operation_ids': [(5, 0, 0)]})
        
        # Set dependencies based on sequence
        previous_op = False
        for operation in operations:
            if previous_op:
                # Current operation is blocked by the previous one
                operation.write({
                    'blocked_by_operation_ids': [(4, previous_op.id, 0)]
                })
            previous_op = operation
            
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Operation dependencies have been set based on sequence.'),
                'sticky': False,
                'type': 'success',
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }
