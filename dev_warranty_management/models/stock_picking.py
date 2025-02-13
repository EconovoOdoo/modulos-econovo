from odoo import models, api, _

class StockPicking(models.Model):
    _inherit = "stock.picking"

    def button_validate(self):
        res = super(StockPicking, self).button_validate()
        # Procesamos solo los albaranes de salida (entregas)
        for picking in self.filtered(lambda p: p.picking_type_code == 'outgoing'):
            # Recorremos las líneas de movimiento con cantidad entregada y que requieran garantía
            for move_line in picking.move_line_ids.filtered(lambda ml: ml.product_id.allow_warranty and ml.qty_done > 0):
                # Obtenemos la orden de venta asociada, ya sea desde la línea o el picking
                sale_order = move_line.sale_line_id.order_id if move_line.sale_line_id else picking.sale_id
                delivered_qty = move_line.qty_done
                # Crear una garantía por cada unidad entregada
                for _ in range(int(delivered_qty)):
                    warranty_vals = {
                        'customer_id': sale_order.partner_id.id if sale_order else False,
                        'sale_id': sale_order.id if sale_order else False,
                        'product_id': move_line.product_id.id,
                        'quantity': 1,
                        'activation_method': 'deliver_product',
                        'serial_no_id': move_line.lot_id.id if move_line.lot_id else False,
                        'warranty_period': move_line.product_id.warranty_period,
                        'waranty_type': move_line.product_id.waranty_type,
                        'waranty_charges': move_line.product_id.waranty_charges,
                    }
                    warranty = self.env['warranty.warranty'].create(warranty_vals)
                    warranty.onchange_customer_id()
                    warranty.onchange_sale_id()
                    warranty.onchange_product_id()
        return res
