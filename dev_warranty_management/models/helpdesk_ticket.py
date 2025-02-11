# See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class helpdesk_ticket(models.Model):
	_inherit = 'helpdesk.ticket'
	
	number = fields.Char(string='Number',default='/')
	warranty_id = fields.Many2one('warranty.warranty',string='Customer Warranty')
	issue_file = fields.Binary(string='Issue File')
	product_id = fields.Many2one('product.product',string='Product')
	sale_id = fields.Many2one('sale.order',string='Sale Order')
	waranty_type = fields.Selection([('free','Free'),('paid','Paid')],default='free'
									,string='Warranty Type')
	start_date = fields.Date(string='Start Date')
	end_date = fields.Date(string='End Date')
	is_warranty_ticket = fields.Boolean(string='Is Warranty Ticket')
	repair_count = fields.Integer(string='Repair Count', compute='_compute_repair_count')
	repair_id = fields.Many2one('repair.order', string='Repair Order')
	repair_ticket_flag = fields.Boolean(string='Repair Ticket Flag')
	task_count = fields.Integer(compute="get_task_count",string="Tasks")
	

	@api.model
	def create(self, vals):
		res = super(helpdesk_ticket, self).create(vals)
		sequence = self.env['ir.sequence'].next_by_code('helpdesk.ticket.waranty') or 'New'
		res.number = sequence
		return res
	
	
	def action_view_warranty(self):
		warranty_ids = self.warranty_id or False
		action = self.env.ref('dev_warranty_management.action_warranty_warranty').read()[0]
		if len(warranty_ids) > 1:
			action['domain'] = [('id', 'in', warranty_ids.ids)]
		else:
			action['views'] = [(self.env.ref('dev_warranty_management.form_warranty_warranty').id, 'form')]
			action['res_id'] = warranty_ids.id
		return action


	@api.onchange('warranty_id')
	def _onchange_warranty_id(self):

		self.sale_id = self.warranty_id.sale_id.id
		self.waranty_type = self.warranty_id.waranty_type
		self.start_date = self.warranty_id.start_date
		self.end_date = self.warranty_id.end_date
		self.product_id = self.warranty_id.product_id.id
		self.partner_id = self.warranty_id.customer_id.id



	def _compute_repair_count(self):
		for order in self:
			repair_ids = self.env['repair.order'].search([('repair_ticket_id','=',self.id)])
			order.repair_count = len(repair_ids)


	def action_view_repair(self):
		action = self.env.ref('repair.action_repair_order_tree').read()[0]
		repair_ids = self.env['repair.order'].search([('repair_ticket_id','=',self.id)])
		if len(repair_ids) > 1:
		    action['domain'] = [('id', 'in', repair_ids.ids)]
		elif repair_ids:
		    action['views'] = [(self.env.ref('repair.view_repair_order_form').id, 'form')]
		    action['res_id'] = repair_ids.id
		return action

	def create_repair_order(self):
		for data in self:
			return {
			'name': _('Repair Orders'),
			'view_mode': 'form',
			'res_model': 'repair.order',
			'view_id': self.env.ref('repair.view_repair_order_form').id,
			'type': 'ir.actions.act_window',
			'context': {
			'default_partner_id': self.partner_id and self.partner_id.id or False,
			'default_repair_ticket_id':self.id,
			'default_sale_order_id':self.sale_id.id,
			'default_product_id':self.product_id.id,
			'default_warranty_id':self.warranty_id.id,
			},
			'target': 'new'
		}
		

	def view_tasks(self):
		task_ids = self.env['project.task'].search([('ticket_id', '=', self.id)])
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
			task_ids = self.env['project.task'].search([('ticket_id', '=',count.id)])  
			count.task_count = len(task_ids)   
	
	
	
#    allow_warranty_renewal = fields.Boolean(string='Warranty Renewal')
	
   
   
		
