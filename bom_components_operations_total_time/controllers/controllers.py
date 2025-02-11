# -*- coding: utf-8 -*-
# from odoo import http


# class BomComponentsOperationsTotalTime(http.Controller):
#     @http.route('/bom_components_operations_total_time/bom_components_operations_total_time', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/bom_components_operations_total_time/bom_components_operations_total_time/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('bom_components_operations_total_time.listing', {
#             'root': '/bom_components_operations_total_time/bom_components_operations_total_time',
#             'objects': http.request.env['bom_components_operations_total_time.bom_components_operations_total_time'].search([]),
#         })

#     @http.route('/bom_components_operations_total_time/bom_components_operations_total_time/objects/<model("bom_components_operations_total_time.bom_components_operations_total_time"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('bom_components_operations_total_time.object', {
#             'object': obj
#         })

