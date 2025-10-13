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
            
            move_ids = self.env.context.get('default_move_ids', [])
            source_picking_names = []
            
            if move_ids:
                moves = self.env['stock.move'].browse(move_ids)
                picking_names = moves.mapped('picking_id.name')
                source_picking_names.extend([name for name in picking_names if name])
            
            if not source_picking_names:
                picking_ids = self.env.context.get('default_picking_ids', [])
                if picking_ids:
                    pickings = self.env['stock.picking'].browse(picking_ids)
                    picking_names = pickings.mapped('name')
                    source_picking_names.extend([name for name in picking_names if name])
            
            if not source_picking_names:
                active_model = self.env.context.get('active_model')
                active_id = self.env.context.get('active_id')
                
                if active_model == 'stock.picking' and active_id:
                    picking = self.env['stock.picking'].browse(active_id)
                    if picking.exists():
                        source_picking_names.append(picking.name)
            
            if not source_picking_names and hasattr(self, 'move_ids') and self.move_ids:
                picking_names = self.move_ids.mapped('picking_id.name')
                source_picking_names.extend([name for name in picking_names if name])
            
            unique_picking_names = list(set(source_picking_names))
            if unique_picking_names:
                data['source_picking_info'] = unique_picking_names
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