# -*- coding: utf-8 -*-

from odoo import models, fields, api, _

class ProductLabelLayout(models.TransientModel):
    _inherit = 'product.label.layout'

    print_format = fields.Selection(
        selection_add=[('dymo_100x70', 'DYMO Etiqueta 100x70')],
        ondelete={'dymo_100x70': 'set default'},
    )

    def _prepare_report_data(self):
        xml_id, data = super()._prepare_report_data()
        
        if self.print_format == 'dymo_100x70':
            xml_id = 'econovo_dymo_labels.action_report_dymo_labels'
            if not data:
                data = {}
            data.update({
                'quantity': self.custom_quantity or 1,
                'active_model': 'product.product',
                'print_format': self.print_format,
            })
            
            # Asegurarse de que tenemos los productos correctos
            if self.product_ids:
                products = self.product_ids
            elif self.product_tmpl_ids:
                products = self.env['product.product'].search([
                    ('product_tmpl_id', 'in', self.product_tmpl_ids.ids)
                ])
            else:
                products = self.env['product.product'].browse()
            
            data['active_ids'] = products.ids
        
        return xml_id, data