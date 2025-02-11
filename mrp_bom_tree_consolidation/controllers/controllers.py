# -*- coding: utf-8 -*-
# from odoo import http


# class MrpBomTreeConsolidation(http.Controller):
#     @http.route('/mrp_bom_tree_consolidation/mrp_bom_tree_consolidation', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/mrp_bom_tree_consolidation/mrp_bom_tree_consolidation/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('mrp_bom_tree_consolidation.listing', {
#             'root': '/mrp_bom_tree_consolidation/mrp_bom_tree_consolidation',
#             'objects': http.request.env['mrp_bom_tree_consolidation.mrp_bom_tree_consolidation'].search([]),
#         })

#     @http.route('/mrp_bom_tree_consolidation/mrp_bom_tree_consolidation/objects/<model("mrp_bom_tree_consolidation.mrp_bom_tree_consolidation"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('mrp_bom_tree_consolidation.object', {
#             'object': obj
#         })

