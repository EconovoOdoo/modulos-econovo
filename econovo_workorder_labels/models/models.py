# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class MrpWorkOrder(models.Model):
    _inherit = 'mrp.workorder'
    
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