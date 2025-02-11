# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#s
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

from odoo import fields, models,api,_

class repair_order(models.Model):
    _inherit = 'repair.order'
    
    repair_ticket_count = fields.Integer(string='Ticket Count', compute='_compute_repair_ticket_count')
    repair_ticket_id = fields.Many2one('helpdesk.ticket', string='Ticket')
    warranty_id = fields.Many2one('warranty.warranty', string='Warranty')
    
    
    def _compute_repair_ticket_count(self):
        for order in self:
            repair_ticket_ids = self.env['helpdesk.ticket'].search([('id','=',self.repair_ticket_id.id)])
            order.repair_ticket_count = len(repair_ticket_ids)

    @api.model
    def create(self,vals):
        repair_id = super(repair_order,self).create(vals)
        if repair_id.repair_ticket_id:
            attachment_ids = self.env['ir.attachment'].search([('res_id','=',repair_id.repair_ticket_id.id),
                                                               ('res_model','=','helpdesk.ticket')])
            if attachment_ids:
                for att in attachment_ids:
                    att.copy({'res_model': 'repair.order','res_id':repair_id.id})
        return repair_id

    def create_repair_ticket(self):
        for data in self:
            return {
                'name': _('Ticket'),
                'view_mode': 'form',
                'res_model': 'helpdesk.ticket',
                'view_id': self.env.ref('helpdesk.helpdesk_ticket_view_form').id,
                'type': 'ir.actions.act_window',
                'context': {
                            'default_partner_id': self.partner_id and self.partner_id.id or False,
                            'default_repair_ticket_flag': True,
                            'default_repair_ticket_id': self.id,
                            },
                'target': 'new'
            }
           
    def action_view_inv_ticket(self):
        action = self.env.ref('helpdesk.helpdesk_ticket_action_main_tree').read()[0]
        repair_ids = self.env['helpdesk.ticket'].search([('id','=',self.repair_ticket_id.id)])
        if len(repair_ids) > 1:
            action['domain'] = [('id', 'in', repair_ids.ids)]
        elif repair_ids:
            action['views'] = [(self.env.ref('helpdesk.helpdesk_ticket_view_form').id, 'form')]
            action['res_id'] = repair_ids.id
        return action

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
