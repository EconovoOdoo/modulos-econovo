# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class MrpBomSetDependenciesWizard(models.TransientModel):
    _name = 'mrp.bom.set.dependencies.wizard'
    _description = 'Set Operation Dependencies Wizard'

    @api.model
    def default_get(self, fields):
        res = super(MrpBomSetDependenciesWizard, self).default_get(fields)
        active_ids = self.env.context.get('active_ids', [])
        boms = self.env['mrp.bom'].browse(active_ids)
        
        # Count BOMs with and without dependencies allowed
        allowed_count = len(boms.filtered(lambda b: b.allow_operation_dependencies))
        not_allowed_count = len(boms) - allowed_count
        
        res['bom_count'] = len(boms)
        res['allowed_count'] = allowed_count
        res['not_allowed_count'] = not_allowed_count
        
        return res

    bom_count = fields.Integer(string="Total BOMs", readonly=True)
    allowed_count = fields.Integer(string="BOMs with dependencies allowed", readonly=True)
    not_allowed_count = fields.Integer(string="BOMs without dependencies allowed", readonly=True)
    enable_dependencies = fields.Boolean(
        string="Enable Operation Dependencies", 
        default=False,
        help="If checked, operation dependencies will be enabled for the selected BOMs that don't have this option active"
    )
    
    def confirm_set_dependencies(self):
        """Set dependencies for selected BOMs"""
        active_ids = self.env.context.get('active_ids', [])
        boms = self.env['mrp.bom'].browse(active_ids)
        
        # If enabled, enable operation dependencies for BOMs that don't have it
        if self.enable_dependencies and self.not_allowed_count > 0:
            boms_to_enable = boms.filtered(lambda b: not b.allow_operation_dependencies)
            boms_to_enable.write({
                'allow_operation_dependencies': True
            })
        
        # Get BOMs with dependencies allowed (might include newly enabled ones)
        boms_with_dependencies = boms.filtered(lambda b: b.allow_operation_dependencies)
        
        # Process each BOM
        processed_count = 0
        for bom in boms_with_dependencies:
            bom.action_set_operation_dependencies()
            processed_count += 1
            
        # Create a notification message
        message = _('Operation dependencies have been set for %s BOMs.') % processed_count
        
        # Show notification message
        self.env['bus.bus']._sendone(
            self.env.user.partner_id, 
            'notification', 
            {
                'title': _('Success'),
                'message': message,
                'sticky': False,
                'type': 'success',
            }
        )
        
        # Close dialog
        return {'type': 'ir.actions.act_window_close'}
