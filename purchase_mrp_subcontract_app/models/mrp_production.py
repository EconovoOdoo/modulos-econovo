# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class MrpProduction(models.Model):
	_inherit='mrp.production'

	@api.depends('workorder_ids')
	def _compute_workorder_count(self):
		data = self.env['mrp.workorder'].read_group([('production_id', 'in', self.ids)], ['production_id'], ['production_id'])
		count_data = dict((item['production_id'][0], item['production_id_count']) for item in data)
		for production in self:
			production.workorder_count = count_data.get(production.id, 0)

	@api.depends('workorder_ids.state')
	def _compute_workorder_done_count(self):
		data = self.env['mrp.workorder'].read_group([
			('production_id', 'in', self.ids),
			('state', '=', 'done')], ['production_id'], ['production_id'])
		count_data = dict((item['production_id'][0], item['production_id_count']) for item in data)
		for production in self:
			production.workorder_done_count = count_data.get(production.id, 0)

	is_subcontract = fields.Boolean("Is Subcontract")
	workorder_count = fields.Integer('# Work Orders', compute='_compute_workorder_count')
	workorder_done_count = fields.Integer('# Done Work Orders', compute='_compute_workorder_done_count')