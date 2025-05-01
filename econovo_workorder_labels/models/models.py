# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime

class MrpWorkOrder(models.Model):
    _inherit = 'mrp.workorder'
    
    def get_parent_bom_product(self):
        """Return the immediate parent product"""
        if self.production_id and self.production_id.bom_id:
            return self.production_id.bom_id.product_id
        return False
    
    def get_top_bom_ancestor(self):
        """Return the highest level BOM ancestor"""
        if not self.production_id or not self.production_id.bom_id:
            return False
        
        current_bom = self.production_id.bom_id
        top_bom = current_bom
        
        # Try to find parent BOMs
        while True:
            # Search for any BOM that has current_bom's product as a component
            parent_bom = self.env['mrp.bom'].search([
                ('bom_line_ids.product_id', '=', current_bom.product_id.id)
            ], limit=1)
            
            if parent_bom:
                top_bom = parent_bom
                current_bom = parent_bom
            else:
                break
                
        return top_bom.product_id
        
    def print_workorder_label(self):
        """Action to print the label"""
        self.ensure_one()
        return self.env.ref('econovo_workorder_labels.action_workorder_label_report').report_action(self)


class WorkOrderLabelLayout(models.TransientModel):
    _name = 'workorder.label.layout'
    _description = 'Workorder Label Layout'
    
    workorder_id = fields.Many2one('mrp.workorder', string='Work Order')
    label_quantity = fields.Integer('Quantity', default=1)
    
    def action_print_label(self):
        self.ensure_one()
        return self.env.ref('econovo_workorder_labels.action_workorder_label_report').report_action(self.workorder_id)