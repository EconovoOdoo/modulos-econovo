# -*- coding: utf-8 -*-
# from odoo import http


# class MrpBomCategoryCosts(http.Controller):
#     @http.route('/mrp_bom_category_costs/mrp_bom_category_costs', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/mrp_bom_category_costs/mrp_bom_category_costs/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('mrp_bom_category_costs.listing', {
#             'root': '/mrp_bom_category_costs/mrp_bom_category_costs',
#             'objects': http.request.env['mrp_bom_category_costs.mrp_bom_category_costs'].search([]),
#         })

#     @http.route('/mrp_bom_category_costs/mrp_bom_category_costs/objects/<model("mrp_bom_category_costs.mrp_bom_category_costs"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('mrp_bom_category_costs.object', {
#             'object': obj
#         })

