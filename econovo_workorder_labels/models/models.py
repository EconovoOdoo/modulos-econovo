# -*- coding: utf-8 -*-

from odoo import models, api

class MrpWorkOrder(models.Model):
    _inherit = 'mrp.workorder'
    
    def print_workorder_label(self):
        """Action to print the label"""
        self.ensure_one()
        return self.env.ref('econovo_workorder_labels.action_workorder_label_report').report_action(self)
    
    @api.model
    def action_print_multiple_labels(self):
        """Open wizard to print multiple labels from list view"""
        workorder_ids = self.env.context.get('active_ids', [])
        if not workorder_ids:
            return False
        
        wizard = self.env['workorder.multi.label.layout'].create({
            'workorder_lines': [(0, 0, {'workorder_id': workorder_id, 'label_quantity': 1}) 
                               for workorder_id in workorder_ids]
        })
        
        return {
            'name': 'Print Multiple Work Order Labels',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'workorder.multi.label.layout',
            'res_id': wizard.id,
            'target': 'new',
            'context': self.env.context,
        }