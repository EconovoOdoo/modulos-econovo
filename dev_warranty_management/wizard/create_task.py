# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

import time
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class dev_repair_warranty_task(models.TransientModel):
    _name = "dev.repair.warranty.task"
    _description = "Wizard"
   
    name = fields.Char(string="Name")
    user_id = fields.Many2one('res.users',string="Assigned to",default=lambda self: self.env.user)
    project_id = fields.Many2one('project.project',string="Project")
    date_deadline = fields.Date(string="Deadline",default=fields.Date.today())
    partner_id = fields.Many2one('res.partner',string="Customer")
    tag_ids = fields.Many2many('project.tags',string="Tag")
    description = fields.Html(string="Description")
    
    @api.model
    def default_get(self, fields):
        res = super(dev_repair_warranty_task, self).default_get(fields)
        active_ids = self._context.get('active_ids')
        ticket = self.env['helpdesk.ticket'].browse(active_ids)
        if ticket:
            res.update({
                'partner_id': ticket.partner_id.id,
            })
        return res


    def create_task(self):
        active_ids = self._context.get('active_ids')
        ticket = self.env['helpdesk.ticket'].browse(active_ids)
        vals={
            'name':self.name,
            'user_ids':self.user_id and self.user_id.ids,
            'date_deadline':self.date_deadline,
            'partner_id':self.partner_id and self.partner_id.id,
            'project_id':self.project_id and self.project_id.id,
            'tag_ids':self.tag_ids and self.tag_ids.ids,
            'description':self.description,
            'ticket_id':ticket and ticket.id,
            'warranty_id':ticket and ticket.warranty_id.id or False,
             }
        task_id = self.env['project.task'].create(vals)
        print("task_id====",task_id)
        return True
       
       
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:




