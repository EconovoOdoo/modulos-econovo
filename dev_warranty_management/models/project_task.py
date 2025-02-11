# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

from odoo import models, fields, api


class project_task(models.Model):
    _inherit = 'project.task'

    ticket_id = fields.Many2one('helpdesk.ticket',string="Ticket")
   # ticket_counter = fields.Integer(string="Ticket")
    ticket_counter = fields.Integer(string="Ticket",compute="get_ticket_count")
    warranty_id = fields.Many2one('warranty.warranty', string='Warranty')

    def view_tickets(self):
        ticket_ids = self.env['helpdesk.ticket'].search([('id', '=', self.ticket_id.id)])
        action = self.env["ir.actions.actions"]._for_xml_id('dev_warranty_management.action_all_ticket')
        if len(ticket_ids) > 1:
            action['domain'] = [('id', 'in', ticket_ids.ids)]
        elif len(ticket_ids) == 1:
            action['views'] = [(self.env.ref('helpdesk.helpdesk_ticket_view_form').id, 'form')]
            action['res_id'] = ticket_ids[0].id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def get_ticket_count(self):   
        for count in self:
            ticket_ids = self.env['helpdesk.ticket'].search([('id', '=',count.ticket_id.id)])  
            count.ticket_counter = len(ticket_ids)
          
             
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
