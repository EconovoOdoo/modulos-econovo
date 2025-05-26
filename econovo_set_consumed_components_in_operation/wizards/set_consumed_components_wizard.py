# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SetConsumedComponentsWizard(models.TransientModel):
    _name = 'set.consumed.components.wizard'
    _description = 'Set Consumed Components in Operation Wizard'

    @api.model
    def default_get(self, fields):
        res = super(SetConsumedComponentsWizard, self).default_get(fields)
        active_ids = self.env.context.get('active_ids', [])
        boms = self.env['mrp.bom'].browse(active_ids)
        
        # Count BOMs and their operations status
        bom_count = len(boms)
        boms_with_operations = boms.filtered(lambda b: b.operation_ids)
        boms_without_operations = boms - boms_with_operations
        
        res['bom_count'] = bom_count
        res['boms_with_operations_count'] = len(boms_with_operations)
        res['boms_without_operations_count'] = len(boms_without_operations)
        
        return res

    bom_count = fields.Integer(string="Total BOMs", readonly=True)
    boms_with_operations_count = fields.Integer(string="BOMs with operations", readonly=True)
    boms_without_operations_count = fields.Integer(string="BOMs without operations", readonly=True)
    
    consumption_type = fields.Selection([
        ('first_operation', 'Consume in first operation'),
        ('last_operation', 'Consume in last operation'),
        ('specific_sequence', 'Consume in specific operation sequence')
    ], string="Consumption Type", required=True, default='first_operation')
    
    operation_sequence = fields.Integer(
        string="Operation Sequence", 
        help="Sequence number of the operation where components will be consumed"
    )
    
    @api.onchange('consumption_type')
    def _onchange_consumption_type(self):
        """Clear operation_sequence when not needed"""
        if self.consumption_type != 'specific_sequence':
            self.operation_sequence = False
    
    def confirm_set_consumed_components(self):
        """Set component consumption for selected BOMs"""
        active_ids = self.env.context.get('active_ids', [])
        boms = self.env['mrp.bom'].browse(active_ids)
        
        # Validate specific sequence input
        if self.consumption_type == 'specific_sequence' and not self.operation_sequence:
            raise UserError(_("Please specify the operation sequence number."))
        
        if self.consumption_type == 'specific_sequence' and self.operation_sequence <= 0:
            raise UserError(_("Operation sequence must be greater than 0."))
        
        # Process each BOM
        processed_boms = 0
        processed_components = 0
        skipped_boms = []
        
        for bom in boms:
            try:
                components_count = self._process_bom_components(bom)
                if components_count > 0:
                    processed_boms += 1
                    processed_components += components_count
                else:
                    skipped_boms.append(bom.display_name)
            except Exception as e:
                skipped_boms.append(f"{bom.display_name}: {str(e)}")
        
        # Create notification message
        message_parts = []
        if processed_boms > 0:
            message_parts.append(_('Components consumption set for %s BOMs (%s components total).') % (processed_boms, processed_components))
        
        if skipped_boms:
            message_parts.append(_('Skipped BOMs: %s') % ', '.join(skipped_boms))
        
        message = '\n'.join(message_parts) if message_parts else _('No components were processed.')
        
        # Show notification
        self.env['bus.bus']._sendone(
            self.env.user.partner_id, 
            'notification', 
            {
                'title': _('Success') if processed_boms > 0 else _('Warning'),
                'message': message,
                'sticky': False,
                'type': 'success' if processed_boms > 0 else 'warning',
            }
        )
        
        return {'type': 'ir.actions.act_window_close'}
    
    def _process_bom_components(self, bom):
        """Process components for a single BOM"""
        if not bom.bom_line_ids:
            return 0
        
        operations = bom.operation_ids.sorted(key=lambda r: r.sequence)
        
        if not operations:
            # BOM has no operations - skip
            return 0
        
        # Determine target operation
        target_operation = self._get_target_operation(operations)
        if not target_operation:
            raise UserError(_("Operation with sequence %s not found in BOM %s") % (self.operation_sequence, bom.display_name))
        
        # Update all components in this BOM
        bom.bom_line_ids.write({
            'operation_id': target_operation.id
        })
        
        return len(bom.bom_line_ids)
    
    def _get_target_operation(self, operations):
        """Get the target operation based on consumption type"""
        if self.consumption_type == 'first_operation':
            return operations[0] if operations else False
        elif self.consumption_type == 'last_operation':
            return operations[-1] if operations else False
        elif self.consumption_type == 'specific_sequence':
            return operations.filtered(lambda op: op.sequence == self.operation_sequence)[:1]
        return False
