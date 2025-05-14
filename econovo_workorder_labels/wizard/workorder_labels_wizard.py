# -*- coding: utf-8 -*-

from odoo import models, fields

class WorkOrderLabelLayout(models.TransientModel):
    _name = 'workorder.label.layout'
    _description = 'Workorder Label Layout'
    
    workorder_id = fields.Many2one('mrp.workorder', string='Work Order')
    label_quantity = fields.Integer('Quantity', default=1)
    
    def action_print_label(self):
        self.ensure_one()
        return self.env.ref('econovo_workorder_labels.action_workorder_label_report').report_action(self.workorder_id)


class WorkOrderMultiLabelLine(models.TransientModel):
    _name = 'workorder.multi.label.line'
    _description = 'Work Order Label Line'
    
    wizard_id = fields.Many2one('workorder.multi.label.layout', string='Wizard')
    workorder_id = fields.Many2one('mrp.workorder', string='Work Order', required=True)
    product_id = fields.Many2one(related='workorder_id.product_id', string='Product', readonly=True)
    production_id = fields.Many2one(related='workorder_id.production_id', string='Production Order', readonly=True)
    name = fields.Char(related='workorder_id.name', string='Operation', readonly=True)
    workcenter_id = fields.Many2one(related='workorder_id.workcenter_id', string='Work Center', readonly=True)
    label_quantity = fields.Integer('Label Quantity', default=1, required=True)


class WorkOrderMultiLabelLayout(models.TransientModel):
    _name = 'workorder.multi.label.layout'
    _description = 'Multiple Workorders Label Layout'
    
    workorder_lines = fields.One2many('workorder.multi.label.line', 'wizard_id', string='Work Orders')
    
    def action_print_multi_labels(self):
        """Print multiple labels with different quantities"""
        workorders = []
        for line in self.workorder_lines:
            for _ in range(line.label_quantity):
                workorders.append(line.workorder_id.id)
        
        if not workorders:
            return False
        
        return self.env.ref('econovo_workorder_labels.action_workorder_label_report').report_action(
            self.env['mrp.workorder'].browse(workorders)
        )
