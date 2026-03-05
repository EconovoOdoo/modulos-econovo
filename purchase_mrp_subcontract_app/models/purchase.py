# -*- coding: utf-8 -*-

from odoo import api, fields, models, _

class Purchase(models.Model):
	_inherit = 'purchase.order'

	is_mo_order = fields.Boolean('Is MO Order')