# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class MrpWorkCenter(models.Model):
	_inherit='mrp.workcenter'

	is_subcontract = fields.Boolean("Subcontracting")
	partner_id = fields.Many2one('res.partner', string="Contract Partner")
	product_id = fields.Many2one('product.product', string="Contract Service")
	cost = fields.Float("Cost Per Quantity")
	picking_type_id = fields.Many2one('stock.picking.type', string="Picking Type")
	return_type_id = fields.Many2one('stock.picking.type', string="Return Type")

	@api.onchange('product_id')
	def get_service_cost(self):
		if self.product_id:
			self.cost = self.product_id.lst_price

