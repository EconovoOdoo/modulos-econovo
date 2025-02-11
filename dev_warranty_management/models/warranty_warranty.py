# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from dateutil.relativedelta import relativedelta
from datetime import timedelta
from odoo.exceptions import ValidationError,UserError

class warranty_warranty(models.Model):
    _name = 'warranty.warranty'
    _inherit = ['mail.thread', 'mail.activity.mixin','portal.mixin']
    _description = 'Warranty Registration'
    _rec_name = 'number'
    _order = 'id desc'

    def _compute_access_url(self):
        super(warranty_warranty, self)._compute_access_url()
        for data in self:
            data.access_url = '/my/warranty/%s' % (data.id)

    def _get_report_base_filename(self):
        self.ensure_one()
        return '%s %s' % (_('Warranty Card'), self.number)

    number = fields.Char(string="Number",default='/')
    customer_id = fields.Many2one('res.partner', string='Customer')
    mobile = fields.Char(string='Mobile')
    email = fields.Char(string='Email')

    sale_id = fields.Many2one('sale.order', string='Sale Order')
    serial_no_id = fields.Many2one('stock.lot', string='Serial No')
    product_id = fields.Many2one('product.product', string='Product')
    warranty_period = fields.Integer(string='Warranty Period(In Months)')
    waranty_type = fields.Selection([('free','Free'),('paid','Paid')],default='free'
                                    ,string='Warranty Type')
    waranty_charges = fields.Float(string='Paid Charges')
    quantity = fields.Float(string='Quantity')
    uom_id = fields.Many2one('uom.uom',string='Unit Of Measure')
    date = fields.Date(String="Date" ,default=fields.Datetime.now)
    start_date = fields.Date(string='Start Date',default=fields.Datetime.now)
    end_date = fields.Date(string='End Date')
    state = fields.Selection([('draft','Draft'),('running','Running'),('invoiced','Invoiced'),('cancel','Cancelled'),
                              ('expire','Expired')],default='draft',string='Status')

    currency_id = fields.Many2one('res.currency', default=lambda self:self.env.user.company_id.currency_id.id)
    user_id = fields.Many2one('res.users', string='Salesperson', default=lambda self:self.env.user.id,track_sequence=2, track_visibility='onchange', index=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self:self.env.user.company_id.id)
    note = fields.Char(string="Note..")
    ticket_ids = fields.One2many('helpdesk.ticket','warranty_id',string='Tickets')
    invoice_id = fields.Many2one('account.move', string='Invoice',copy=False)
    warranty_renewal = fields.Boolean(string='Warranty Renewal')
    warranty_renewal_id = fields.Many2one('warranty.warranty',string='Warranty Renewal')
    warranty_source = fields.Char(string='Source')
    rene_warranty_count = fields.Integer(string='Renewal Warranty Count')
    claim_count = fields.Integer(compute="get_claim_count",string="Claims")
    repair_count = fields.Integer(string='Repair', compute='_compute_repair_count')
    task_count = fields.Integer(compute="get_task_count",string="Tasks")
    warranty_details_id = fields.Many2one("warranty.details",string="Warranty")
    warranty_history_ids = fields.One2many('warranty.history', 'warranty_id', string="Warranty History")
    is_renewed = fields.Boolean(string="Is renewed")
    hide_renewal_button = fields.Boolean(string="Hide renewal button",compute="compute_hide_renewal_button")
    note = fields.Text(string='Policy Details')
    policy_id = fields.Many2one('warranty.policy',string="Policy")
    
    
    
    @api.onchange('policy_id')
    def onchange_policy_id(self):
        for policy in self:
            policy.note = policy.policy_id and policy.policy_id.note or False

    def compute_hide_renewal_button(self):
        for rec in self:
            warranty = rec.env['warranty.warranty'].search_count([('sale_id','=',rec.sale_id.id)
                                                            ,('product_id','=',rec.product_id.id)
                                                            ,('customer_id','=',rec.customer_id.id)
                                                            ,('id','!=',rec.id)
                                                             ])
            if rec.product_id.renewal_time == warranty:
                rec.hide_renewal_button = True
            else:
                rec.hide_renewal_button = False


    @api.model
    def create(self, vals):
        res = super(warranty_warranty, self).create(vals)
        sequence = self.env['ir.sequence'].next_by_code('warranty.warranty') or 'New'
        res.number = sequence
        return res

    @api.onchange('customer_id')
    def onchange_customer_id(self):
        for data in self:
            data.mobile = data.customer_id and data.customer_id.mobile or ' '
            data.email = data.customer_id and data.customer_id.email or ' '


    @api.onchange('sale_id')
    def onchange_sale_id(self):
        for data in self:
            domain = {}
            product_ids = []
            if data.sale_id:
                for line in data.sale_id.order_line:
                    if line.product_id.allow_warranty:
                        product_ids.append(line.product_id and line.product_id.id)
            domain['product_id'] = [('id', 'in', product_ids)]
            return  {'domain': domain}

    @api.onchange('product_id')
    def onchange_product_id(self):
        for data in self:
            sale_id = data.sale_id and data.sale_id.id or False
            product_id = data.product_id and data.product_id.id or False
            so_line_id = self.env['sale.order.line'].search([('order_id','=',sale_id),
                                                             ('product_id','=',product_id)],limit=1)
            data.quantity = so_line_id.product_uom_qty
            data.uom_id = so_line_id.product_uom and so_line_id.product_uom.id or False
            if product_id:
                 data.warranty_details_id = data.product_id and data.product_id.warranty_details_id and data.product_id.warranty_details_id.id or False
            data.warranty_period = data.product_id and data.product_id.warranty_period
            data.waranty_type = data.product_id and data.product_id.waranty_type
            data.waranty_charges = data.product_id and data.product_id.waranty_charges
            end_data = False
            if data.warranty_period:
                end_data = data.start_date + relativedelta(months=data.warranty_period)
            data.end_date = end_data

    def action_confirm(self):
        for data in self:
            data.state = 'confirm'
        return True

    def action_running(self):
        for data in self:
            if data.serial_no_id:
                data.serial_no_id.warranty_details_id = data.product_id.warranty_details_id.id
                data.serial_no_id.waranty_type = data.product_id.waranty_type
                data.serial_no_id.waranty_charges = data.product_id.waranty_charges
                data.serial_no_id.warranty_period = data.product_id.warranty_period
            data.state = 'running'
        return True

    def prepare_invoice_vals(self):
        vals={
            'partner_id':self.customer_id and self.customer_id.id or False,
            #            'account_id':self.customer_id.property_account_receivable_id and self.customer_id.property_account_receivable_id.id or False,
            #            'journal_id':journal_id and journal_id.id,
            'company_id':self.company_id and self.company_id.id or False,
            'currency_id':self.currency_id and self.currency_id.id or False,
            'user_id':self.env.user and self.env.user.id or False,
            'invoice_date':fields.Date.today(),
            'invoice_origin':self.number,
            'move_type':'out_invoice',
        }
        return vals
    def prepare_invoice_line(self,invoice_id):
        product_id = self.product_id
        #        tax_ids = self.product_id.tax_ids
        inv_pool = self.env['account.move'].sudo()
        account_id = product_id.property_account_income_id or product_id.categ_id.property_account_income_categ_id
        if not account_id and product_id:
            raise UserError(_('Please define income account for this product: "%s" (id:%d) - or for its category: "%s".') %
                            (product_id.name, product_id.id, product_id.categ_id.name))
        vals={
            'product_id':product_id and product_id.id or False,
            'account_id':account_id and account_id.id or False,
            'quantity':1,
            'price_unit':self.waranty_charges or 0.0,
            'name':product_id.display_name or 'Warranty Charges',
            #            'tax_ids':[(6,0, tax_ids.ids)],
        }
        return vals

    def action_done(self):
        for data in self:
            if data.waranty_type == 'paid':
                inv_val =  self.prepare_invoice_vals()
                invoice_id = self.env['account.move'].sudo().create(inv_val)
                inv_line_val = self.prepare_invoice_line(invoice_id)
                invoice_id.invoice_line_ids = [(0,0,inv_line_val)]
                self.invoice_id = invoice_id and invoice_id.id or False
                data.state = 'invoiced'
            #else:
              #  data.state = 'done'
        return True

    def action_inv_done(self):
        for data in self:
            data.state = 'done'
        return True

    def action_cancel(self):
        for data in self:
            data.state = 'cancel'
        return True

    def action_draft(self):
        for data in self:
            data.state = 'draft'
        return True

    def action_close(self):
        for data in self:
            data.state = 'close'
        return True

    def action_expire(self):
        for data in self:
            data.state = 'expire'
        return True

    def view_sale_order(self):
        for data in self:
            data.state = 'confirm'
        return True


    def action_view_sale_order(self):
        action = self.env.ref('sale.action_quotations_with_onboarding').read()[0]
        if self.sale_id:
            action['views'] = [(self.env.ref('sale.view_order_form').id, 'form')]
            action['res_id'] = self.sale_id and self.sale_id.id or False
        return action

    def action_view_all_claim(self):
        action = self.env.ref('dev_warranty_management.action_all_ticket').read()[0]
        if len(self.ticket_ids.ids) > 1:
            action['domain'] = [('id', 'in', self.ticket_ids.ids)]
        else:
            action['views'] = [(self.env.ref('helpdesk.helpdesk_ticket_view_form').id, 'form')]
            action['res_id'] = self.ticket_ids.id
        return action

    def get_claim_count(self):
        for count in self:
            ticket_ids = self.env['helpdesk.ticket'].search([('warranty_id', '=',count.id)])
            count.claim_count = len(ticket_ids)

    def action_view_invoice(self):
        action = self.env.ref('account.action_move_out_invoice_type').read()[0]
        action['views'] = [(self.env.ref('account.view_move_form').id, 'form')]
        action['res_id'] = self.invoice_id and self.invoice_id.id or False
        return action


    def send_warranty_exp_reminder(self):
        date = fields.Date.today() + timedelta(days=self.env.user.company_id.warranty_expiry_day)
        warranty_ids = self.env['warranty.warranty'].search([('end_date','=',date),('state','=','running')])
        template_id = self.env.ref('dev_warranty_management.warranty_expiry_reminder_template')
        for warranty in warranty_ids:
            template_id.send_mail(warranty.id,force_send=True)
        return True

    def cron_warranty_expired(self):
        date = fields.Date.today()
        warranty_ids = self.env['warranty.warranty'].search([('end_date','=',date),('state','!=','draft')])
        for warranty in warranty_ids:
            warranty.action_expire()
        return True

    def action_renewal(self):
        for data in self:
            if data.product_id.allow_warranty_renewal:
                if not (data.product_id.renewal_time == 0) and data.product_id.renewal_time <= data.rene_warranty_count:
                    raise ValidationError(_('Renewal Time is Over'))
                else:
                    rene_warranty_id = data.copy()
                    rene_warranty_id.warranty_renewal = True
                    data.warranty_renewal_id = rene_warranty_id and rene_warranty_id.id or False
                    rene_warranty_id.warranty_source = data.number
                    data.rene_warranty_count += 1
                    rene_warranty_id.start_date = data.end_date + relativedelta(days=1)
                    end_data = ''
                    if data.warranty_period:
                        end_data = rene_warranty_id.start_date + relativedelta(months=data.warranty_period)
                    rene_warranty_id.end_date = end_data
                    self.is_renewed = True

                    previous_warranty_ids = self.search([('sale_id','=',rene_warranty_id.sale_id.id)
                                                        ,('product_id','=',rene_warranty_id.product_id.id)
                                                        ,('customer_id','=',rene_warranty_id.customer_id.id)
                                                        ,('id','!=',rene_warranty_id.id)])
                    for history in previous_warranty_ids:
                        rene_warranty_id.warranty_history_ids = [(0, 0, {
                            'start_date': history.start_date,
                            'end_date': history.end_date,
                            'base_warranty_id': history.id,
                        })]

                return {
                        'view_mode': 'form',
                        'res_id': rene_warranty_id.id,
                        'res_model': 'warranty.warranty',
                        'view_type': 'form',
                        'type': 'ir.actions.act_window',
                        'context': self._context,
                        #            'target': 'new',
                    }
        return True


    def action_view_renewal_warranty(self):
        action = self.env.ref('dev_warranty_management.action_warranty_warranty').read()[0]
        action['views'] = [(self.env.ref('dev_warranty_management.form_warranty_warranty').id, 'form')]
        action['res_id'] = self.warranty_renewal_id and self.warranty_renewal_id.id
        return action


    def _compute_repair_count(self):
        for order in self:
            repair_ids = self.env['repair.order'].search([('warranty_id','=',self.id)])
            order.repair_count = len(repair_ids)


    def action_view_repair(self):
        action = self.env.ref('repair.action_repair_order_tree').read()[0]
        repair_ids = self.env['repair.order'].search([('warranty_id','=',self.id)])
        if len(repair_ids) > 1:
            action['domain'] = [('id', 'in', repair_ids.ids)]
        elif repair_ids:
            action['views'] = [(self.env.ref('repair.view_repair_order_form').id, 'form')]
            action['res_id'] = repair_ids.id
        return action


    def view_tasks(self):
        task_ids = self.env['project.task'].search([('warranty_id', '=', self.id)])
        action = self.env["ir.actions.actions"]._for_xml_id('project.action_view_all_task')
        if len(task_ids) > 1:
            action['domain'] = [('id', 'in', task_ids.ids)]
        elif len(task_ids) == 1:
            action['views'] = [(self.env.ref('project.view_task_form2').id, 'form')]
            action['res_id'] = task_ids[0].id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action


    def get_task_count(self):
        for count in self:
            task_ids = self.env['project.task'].search([('warranty_id', '=',count.id)])
            count.task_count = len(task_ids)


    def _get_rating_value(self):
        for request in self:
            request.write({
                'feedback_rate': False,
                'feedback_date': False,
                'rating_image': False,
                'review': '',
                'rating_text': False
            })
            rating_id = self.env['rating.rating'].search([('res_id', '=', self.id),
                                                          ('res_model', '=', 'warranty.warranty')], order='id desc',
                                                         limit=1)
            if rating_id:
                rating = int(rating_id.rating)
                if rating > 4:
                    rating = 4
                request.write({
                    'feedback_rate': str(rating),
                    'feedback_date': rating_id.write_date,
                    'rating_image': rating_id.rating_image,
                    'review': rating_id.feedback,
                    'rating_text': rating_id.rating_text
                })

    def send_rating_email(self):
        template_id = self.env.ref('dev_warranty_management.rating_warrantyy_template1')
        if template_id:
            self.rating_send_request(template_id, lang=self.customer_id.lang, force_send=True)

    feedback_rate = fields.Selection([('0', '0'), ('1', '1'), ('2', '2'), ('3', '3'), ('4', '4')], default='0',
                                     string='Rate', compute='_get_rating_value', readonly=True)
    feedback_date = fields.Date('Feedback Date', compute='_get_rating_value', readonly=True)
    review = fields.Text('Review', compute='_get_rating_value', readonly=True)
    rating_image = fields.Binary('Image', compute='_get_rating_value', readonly=True)
    rating_text = fields.Selection([
        ('top', 'Satisfied'),
        ('ok', 'Okay'),
        ('ko', 'Dissatisfied'),
        ('none', 'No Rating yet')], string='Rating', readonly=True)



# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

