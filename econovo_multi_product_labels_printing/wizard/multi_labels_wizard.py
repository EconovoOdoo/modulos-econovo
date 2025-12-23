# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ProductMultiLabelLine(models.TransientModel):
    _name = 'product.multi.label.line'
    _description = 'Product Multi Label Line'
    
    wizard_id = fields.Many2one('product.label.layout', string='Wizard', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True, readonly=True)
    quantity = fields.Integer('Cantidad', default=1, required=True)
    default_code = fields.Char(related='product_id.default_code', string='Referencia interna', readonly=True)
    barcode = fields.Char(related='product_id.barcode', string='Código de barras', readonly=True)
    
    def _check_access_rule(self, operation):
        return True
    
    @api.onchange('quantity')
    def _onchange_quantity(self):
        if self.quantity < 1:
            self.quantity = 1

class ProductLabelLayout(models.TransientModel):
    _inherit = 'product.label.layout'

    multi_enable = fields.Boolean('Habilitar múltiples cantidades', default=False,
                                help='Permite especificar diferentes cantidades de etiquetas para cada producto')
    multi_label_line_ids = fields.One2many('product.multi.label.line', 'wizard_id', string='Productos')
    from_stock_quant = fields.Boolean('Desde Stock Quant', default=False,
                                       help='Indica si la impresión se inició desde stock.quant')

    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        active_model = self.env.context.get('active_model')
        active_ids = self.env.context.get('active_ids', [])
        
        # Handle stock.quant: extract products and set them in the wizard
        if active_model == 'stock.quant' and active_ids:
            quants = self.env['stock.quant'].browse(active_ids)
            products = quants.mapped('product_id')
            if products:
                # Set product_ids for the native wizard to work
                res['product_ids'] = [(6, 0, products.ids)]
                # Mark that we're coming from stock.quant (no traceability info)
                res['from_stock_quant'] = True
                # Also set multi_label_line_ids for our multi-quantity feature
                qty = res.get('custom_quantity', 1)
                res['multi_label_line_ids'] = [(0, 0, {
                    'product_id': product.id,
                    'quantity': qty,
                }) for product in products]
        elif not res.get('multi_label_line_ids'):
            # Handle product.product and product.template (original logic)
            products = []
            if active_model == 'product.product':
                products = self.env['product.product'].browse(active_ids)
            elif active_model == 'product.template':
                templates = self.env['product.template'].browse(active_ids)
                products = self.env['product.product'].search([('product_tmpl_id', 'in', templates.ids)])
            
            if products:
                qty = res.get('custom_quantity', 1)
                res['multi_label_line_ids'] = [(0, 0, {
                    'product_id': product.id,
                    'quantity': qty,
                }) for product in products]
        return res

    @api.onchange('multi_enable')
    def _onchange_multi_enable(self):
        if not self.multi_enable:
            self.multi_label_line_ids = [(5, 0, 0)]  # Limpiar las líneas
        elif not self.multi_label_line_ids:
            # Crear líneas si no existen
            products = []
            if self.product_ids:
                products = self.product_ids
            elif self.product_tmpl_ids:
                products = self.env['product.product'].search([
                    ('product_tmpl_id', 'in', self.product_tmpl_ids.ids)
                ])
            
            if products:
                self.multi_label_line_ids = [(0, 0, {
                    'product_id': product.id,
                    'quantity': self.custom_quantity or 1,
                }) for product in products]

    def _prepare_report_data(self):
        xml_id, data = super()._prepare_report_data()
        
        if not data:
            data = {}
        
        # If coming from stock.quant, skip picking/traceability info in labels
        if self.from_stock_quant:
            data['skip_picking_info'] = True
        
        if self.multi_enable and self.multi_label_line_ids:
            # Duplicar los productos según la cantidad especificada
            products_with_quantities = []
            for line in self.multi_label_line_ids:
                if line.product_id and line.quantity > 0:
                    for _ in range(line.quantity):
                        products_with_quantities.append(line.product_id.id)
            
            if products_with_quantities:
                # Reemplazar los productos en el contexto y datos con las cantidades correctas
                data['active_model'] = 'product.product'
                data['active_ids'] = products_with_quantities
                data['quantity'] = 1  # Importante: establecer quantity=1 ya que duplicamos los IDs
        
        return xml_id, data

    def process(self):
        self.ensure_one()
        
        # Si es formato DYMO, usar manejo especial
        if self.print_format == 'dymo_100x70':
            if self.multi_enable and self.multi_label_line_ids:
                # Caso de múltiples etiquetas
                valid_lines = self.multi_label_line_ids.filtered(lambda l: l.product_id and l.quantity > 0)
                if not valid_lines:
                    raise UserError(_('Debe especificar una cantidad mayor a 0 para al menos un producto.'))
                
                # Crear lista de IDs de productos multiplicados por su cantidad
                products_with_quantities = []
                for line in valid_lines:
                    products_with_quantities.extend([line.product_id.id] * line.quantity)
            else:
                # Caso de impresión individual
                if self.product_ids:
                    products = self.product_ids
                elif self.product_tmpl_ids:
                    products = self.env['product.product'].search([
                        ('product_tmpl_id', 'in', self.product_tmpl_ids.ids)
                    ])
                else:
                    products = self.env['product.product'].browse()
                
                # Crear lista con la cantidad especificada para cada producto
                products_with_quantities = []
                quantity = self.custom_quantity or 1
                for product in products:
                    products_with_quantities.extend([product.id] * quantity)

            if not products_with_quantities:
                raise UserError(_('No hay productos seleccionados para imprimir.'))
            
            # Crear el recordset de productos
            products = self.env['product.product'].browse(products_with_quantities)
            
            # Build report data
            report_data = {
                'active_model': 'product.product',
                'active_ids': products.ids,
            }
            
            # If coming from stock.quant, skip picking/traceability info
            if self.from_stock_quant:
                report_data['skip_picking_info'] = True
            
            # Retornar la acción del reporte DYMO
            return self.env.ref('econovo_dymo_labels.action_report_dymo_labels').report_action(
                products, data=report_data
            )
        
        # Para otros formatos, usar el comportamiento estándar
        return super().process()
