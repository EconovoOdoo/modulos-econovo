# -*- coding: utf-8 -*-

# from odoo import models, fields, api


# class mrp_bom_category_costs(models.Model):
#     _name = 'mrp_bom_category_costs.mrp_bom_category_costs'
#     _description = 'mrp_bom_category_costs.mrp_bom_category_costs'

#     name = fields.Char()
#     value = fields.Integer()
#     value2 = fields.Float(compute="_value_pc", store=True)
#     description = fields.Text()
#
#     @api.depends('value')
#     def _value_pc(self):
#         for record in self:
#             record.value2 = float(record.value) / 100

