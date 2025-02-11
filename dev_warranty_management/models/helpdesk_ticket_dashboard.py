# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2015 DevIntelle Consulting Service Pvt.Ltd (<http://www.devintellecs.com>).
#
#    For Module Support : devintelle@gmail.com  or Skype : devintelle
#
##############################################################################

from odoo import models, fields, api, _
import datetime
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from operator import itemgetter

class AccountMove(models.Model):
    _inherit = 'helpdesk.ticket'

#    overdue_days = fields.Float(string="Overdue Day", compute='_compute_duration', readonly=False)

#    @api.depends('invoice_date_due')
#    def _compute_duration(self):
#        days = False
#        for each in self:
#            days = each.invoice_date_due - datetime.datetime.now().date()
#            each.overdue_days = -days.days

    @api.model
    def load_server_data_for_dashboard(self,vals={}):
        all_ticket ,close_ticket, done_ticket,open_tickt ,domain = [], [], [], [] ,[]
#        domain = [('move_type','=','out_invoice'),('state','=','posted')]
        date_val = vals.get('date_opt')

        def sd(date):
            return fields.Datetime.to_string(date)
        
        def previous_week_range(date):
            start_date = date + datetime.timedelta(-date.weekday(), weeks=-1)
            end_date = date + datetime.timedelta(-date.weekday() - 1)
            return {'start_date':start_date.strftime('%Y-%m-%d %H:%M:%S'), 'end_date':end_date.strftime('%Y-%m-%d %H:%M:%S')}

        if vals.get('user_id'):
            domain += [('user_id','=',int(vals.get('user_id')))]
        if vals.get('team_id'):
            domain += [('team_id','=',int(vals.get('team_id')))]
        if vals.get('partner_id'):
            domain += [('partner_id','=',int(vals.get('partner_id')))]

        start_date_ctx = self._context.get('DateFilterStartDate', False)
        end_date_ctx = self._context.get('DateFilterEndDate', False)

        today = fields.Date.today()
        this_week_end_date = fields.Date.to_string(fields.Date.from_string(datetime.datetime.today() + relativedelta(days=-today.weekday())) + datetime.timedelta(days=7))
#         this_week_end_date = sd(datetime.datetime.today() + relativedelta(days=-today.weekday())) + datetime.timedelta(days=7)
        week_ago = datetime.datetime.today() - datetime.timedelta(days=7)
        month_ago = (datetime.datetime.today() - relativedelta(months=1)).strftime('%Y-%m-%d %H:%M:%S')
        starting_of_year = datetime.datetime.now().date().replace(month=1, day=1)    
        ending_of_year = datetime.datetime.now().date().replace(month=12, day=31)

        if start_date_ctx and end_date_ctx:
            domain += [('create_date','>=',start_date_ctx),('create_date','<=',end_date_ctx)]
        if date_val and date_val == 'today':
            domain += [('create_date', '>=', datetime.datetime.strftime(date.today(),'%Y-%m-%d 00:00:00')),
             ('create_date', '<=', datetime.datetime.strftime(date.today(),'%Y-%m-%d 23:59:59'))]
        if date_val and date_val == 'yesterday':
            domain += [('create_date', '>=', datetime.datetime.strftime(date.today() - datetime.timedelta(days=1),'%Y-%m-%d 00:00:00')),
                       ('create_date', '<=', datetime.datetime.strftime(date.today() - datetime.timedelta(days=1),'%Y-%m-%d 23:59:59'))]
        if date_val and date_val == 'current_week':
            domain += [('create_date', '>=', sd(datetime.datetime.today() + relativedelta(days=-today.weekday()))), 
                       ('create_date', '<=', this_week_end_date)]
        if date_val and date_val == 'last_7_days':
            domain += [('create_date', '>=', sd(week_ago)), ('create_date', '<=', sd(datetime.datetime.today()))]
        if date_val and date_val == 'last_week':
            domain += [('create_date', '>=', previous_week_range(datetime.datetime.today()).get('start_date')), ('create_date', '<=', previous_week_range(datetime.datetime.today()).get('end_date'))]
        if date_val and date_val == 'current_month':
            domain += [
                       ("create_date", ">=", sd(today.replace(day=1))),
                       ("create_date", "<=", (today.replace(day=1) + relativedelta(months=1)).strftime('%Y-%m-%d 23:59:59'))
                    ]
        if date_val and date_val == 'current_year':
            domain += [
                       ("create_date", ">=", sd(starting_of_year)),
                       ("create_date", "<=", sd(ending_of_year)),
                    ]
#        all_invoice = self.search_read(domain,
#                     fields=['name','partner_id','invoice_date','invoice_date_due',
#                             'amount_total_signed','amount_residual','state','payment_state','overdue_days'],
#                     order="invoice_date_due desc")
        all_invoice = self.search_read(domain,
                     fields=['name','number','sale_id',
                             'partner_id','email','team_id','user_id','stage_id','create_date'],
                     order="create_date desc")
                 
        
        for each in all_invoice:
            if each.get('stage_id')[0]:
                all_ticket.append(each)
            if each.get('stage_id')[1] in ['Done','Solved']:
                done_ticket.append(each)
            if each.get('stage_id')[1] == 'Cancelled':
                close_ticket.append(each)
            if each.get('stage_id')[1] not in  ['Done','Cancelled','Solved']:
                open_tickt.append(each)

        return {
            'all_invoices':all_invoice,
            'done_ticket': done_ticket,
            'close_ticket': close_ticket,
            'all_ticket': all_ticket,
            'open_tickt':open_tickt,
            'records_body': all_ticket , # all_ticket + cancel_tickt
#                                                                          ('type','in',['bank','cash'])],fields=['name'])
        }
    
    @api.model
    def load_users_and_partners(self):
        return{
               'partners': self.env['res.partner'].sudo().search_read([],['name']),
               'users': self.env['res.users'].sudo().search_read([],['name']),
               'teams': self.env['helpdesk.team'].sudo().search_read([],['name']),
            }
    
    def action_activity_mark_as_done(self):
        res = self.action_done()
        return res

    def action_done_and_schedule_next(self, vals):
        rec_id = self.sudo().create({
            'activity_type_id': vals.get('activity_type'),
            'date_deadline' : vals.get('due_date'),
            'user_id': vals.get('user_id'),
            'summary': vals.get('summary') or '',
            'res_model_id':self.res_model_id.id,
            'res_id': self.res_id,
        })
        res = self.action_done()
        return rec_id

    def action_send_email_by_dashboard(self):
        res = self.action_invoice_sent()
        composer = self.env['mail.compose.message'].with_context({
            'default_composition_mode': 'comment',
            'default_model': res.get('context').get('default_model'),
            'default_res_id': res.get('context').get('default_res_id'),
            'template_id': self.env['mail.template'].browse(res.get('default_template_id')).id or False,
        }).with_user(self.user_id).create({
            'partner_ids': [(4, self.partner_id.id)]
        })
        rec_id = self.env['account.invoice.send'].with_context({'active_ids':[self.id]}).create({
                                                          'is_email': self.env.company.invoice_is_email,
                                                          'is_print': self.env.company.invoice_is_print,
                                                          'invoice_ids' : [self.id],
                                                          'composer_id': composer.id,
                                                          'template_id': self.env['mail.template'].browse(res.get('context').get('default_template_id')).id or False,
                                                    })
        rec_id.onchange_template_id()
        email_send = rec_id.send_and_print_action()
        return True
    
    def action_create_payment_from_dashboard(self,vals):
        account_payment_obj = self.env['account.payment']
        account_journal_obj = self.env['account.journal'].browse(vals.get('journal_id'))
        if account_journal_obj:
            payment_id = account_payment_obj.create({
                'payment_type': 'inbound',
                'partner_id': self.partner_id.id,
                'partner_type': 'customer',
                'ref':self.name,
                'journal_id': account_journal_obj.id or False,
                'amount': vals.get('amount'),
                'payment_method_id': account_journal_obj.inbound_payment_method_ids.id,
            })
            payment_id.action_post()
            self.dev_payment_reconcile(payment_id, [self.id])
        return True
    
    def dev_payment_reconcile(self,payment,invoice_ids):
        if payment and invoice_ids:
            invoice_ids = self.env['account.move'].browse(invoice_ids)
            domain = [('account_internal_type', 'in', ('receivable', 'payable')), ('reconciled', '=', False)]
            payment_lines = payment.line_ids.filtered_domain(domain)
            invoice_move_line = self.env['account.move.line']
            for inv in invoice_ids:
                invoice_move_line += inv.line_ids.filtered_domain(domain)
            (payment_lines + invoice_move_line).reconcile()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
