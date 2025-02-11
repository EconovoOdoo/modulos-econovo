from odoo import models, fields, api


class MrpBomTreeExpanded(models.Model):
    _name = 'mrp.bom.tree.expanded'
    _description = 'Vista Expandida de la Lista de Materiales'

    # campos relacionales:
    bom_id = fields.Many2one('mrp.bom', string='Lista de materiales', required=True, index=True)
    product_id = fields.Many2one('product.product', string='Componente/Producto', required=True, index=True)
    parent_bom_id = fields.Many2one('mrp.bom', string='LdM Padre')
    
    # Campos informativos
    bom_level = fields.Integer(string='Nivel de LdM', default=0)
    product_qty = fields.Float(string='Cantidad Necesaria', default=1.0)
    product_price = fields.Float(string='Precio', compute='_compute_product_price', store=True)
    product_cost = fields.Float(string='Costo', compute='_compute_product_cost', store=True)
    total_operation_time_main = fields.Float(string='Tiempo de Operación', compute='_compute_operation_time_main', store=True)
    total_operation_time = fields.Float(string='Tiempo de Operación', compute='_compute_operation_time', store=True)
    uom_id = fields.Many2one('uom.uom', string='Unidad de Medida', related='product_id.uom_id', store=False)
    
    @api.depends('product_id', 'product_qty', 'uom_id')
    def _compute_product_price(self):
        for record in self:
            record.product_price = record.product_id.lst_price * record.product_qty
            
    @api.depends('product_id', 'product_qty', 'uom_id')
    def _compute_product_cost(self):
        for record in self:
            record.product_cost = record.product_id.standard_price * record.product_qty
            
    @api.depends('bom_id', 'product_qty', 'uom_id')
    def _compute_operation_time_main(self):
        for record in self:
            record.total_operation_time_main = record.bom_id.total_operation_time_main * record.product_qty

    @api.depends('bom_id', 'product_qty', 'uom_id')
    def _compute_operation_time(self):
        for record in self:
            record.total_operation_time = record.bom_id.total_operation_time * record.product_qty

    # Añadir método para actualización manual
    def action_refresh_data(self):
        self.ensure_one()
        self._compute_product_price()
        self._compute_product_cost()
        self._compute_operation_time_main()
        self._compute_operation_time()
        return True


class MrpBom(models.Model):
    _inherit = 'mrp.bom'
    
    def sumarize_bom(self):
        self.ensure_one()
        MrpBomTreeExpanded = self.env['mrp.bom.tree.expanded']
        
        # Limpiamos registros anteriores
        existing_records = MrpBomTreeExpanded.search([])
        existing_records.unlink()
        
        # Diccionario para rastrear productos ya procesados
        processed_products = {}
        
        def process_bom(bom, level=0, parent_bom=False, qty_multiplier=1.0):
            # Obtener el producto correcto de la LdM
            product = bom.product_id or bom.product_tmpl_id.product_variant_id
            if not product:
                return
            
            # Crear registro para el producto principal si no existe
            product_key = (product.id, bom.id, parent_bom.id if parent_bom else False)
            if product_key not in processed_products:
                processed_products[product_key] = MrpBomTreeExpanded.create({
                    'bom_id': bom.id,
                    'product_id': product.id,
                    'parent_bom_id': parent_bom and parent_bom.id or False,
                    'bom_level': level,
                    'product_qty': bom.product_qty * qty_multiplier,
                })
            
            # Procesar componentes
            for line in bom.bom_line_ids:
                if not line.product_id:
                    continue
                
                bom_result = self.env['mrp.bom']._bom_find(
                    line.product_id,
                    company_id=bom.company_id.id,
                )
                
                # Obtener la LdM específica para este producto
                child_bom = bom_result[line.product_id]
                
                # Calcular la cantidad total necesaria
                line_qty = line.product_qty * qty_multiplier
                
                # Crear registro para el componente
                component_key = (line.product_id.id, child_bom.id if child_bom else bom.id, bom.id)
                if component_key not in processed_products:
                    processed_products[component_key] = MrpBomTreeExpanded.create({
                        'bom_id': child_bom.id if child_bom else bom.id,
                        'product_id': line.product_id.id,
                        'parent_bom_id': bom.id,
                        'bom_level': level + 1,
                        'product_qty': line_qty,
                    })
                
                # Procesar la LdM del componente si existe
                if child_bom:
                    process_bom(child_bom, level + 1, bom, line_qty)
        
        process_bom(self)
        
        # Retornar acción para mostrar la vista
        return {
            'name': 'Análisis de Lista de Materiales',
            'type': 'ir.actions.act_window',
            'res_model': 'mrp.bom.tree.expanded',
            'view_mode': 'tree',
            'target': 'current',
        }




    



