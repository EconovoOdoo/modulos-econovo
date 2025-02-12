from odoo import models, fields


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
            products_data = []
            pricelist = self.env['product.pricelist'].search([], limit=1)  # Obtiene una lista de precios por defecto

            for product in self.product_tmpl_ids:
                products_data.append({
                    'id': product.id,
                    'qty': 1
                })

            data.update({
                'products': products_data,
                'product_ids': self.product_tmpl_ids.ids,
                'pricelist': pricelist.id if pricelist else False
            })

        return xml_id, data
