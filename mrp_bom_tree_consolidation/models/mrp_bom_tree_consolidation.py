from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class MrpBomTreeConsolidation(models.Model):
    _name = 'mrp.bom.tree.consolidation'
    _description = 'Consolidación de Componentes de BoM'

    bom_id = fields.Many2one('mrp.bom', string="Lista de Materiales")
    component_id = fields.Many2one('product.product', string="Componente")
    quantity = fields.Float("Cantidad", compute='_compute_quantity', store=False)
    uom_id = fields.Many2one(related='component_id.uom_id', string="Unidad de Medida", store=False)
    level = fields.Integer(string="Nivel", default=0)
    parent_bom_id = fields.Many2one('mrp.bom', string="BOM Padre")
    price = fields.Float(related='component_id.list_price', string="Precio", store=False)
    cost = fields.Float(related='component_id.standard_price', string="Costo", store=False)
    total_operation_time_main = fields.Float(related='bom_id.total_operation_time_main', store=False)
    total_operation_time = fields.Float(related='bom_id.total_operation_time', store=False)
    accumulated_factor = fields.Float("Factor Acumulado", default=1.0)
    last_update = fields.Datetime("Última Actualización", readonly=False)
    needs_refresh = fields.Boolean("Necesita Actualización", compute='_compute_needs_refresh', store=False)

    @api.depends('bom_id', 'bom_id.write_date', 'parent_bom_id', 'parent_bom_id.write_date')
    def _compute_needs_refresh(self):
        """Determina si el registro necesita actualización basado en cambios en las LdM"""
        for record in self:
            record.needs_refresh = (
                (record.bom_id and record.bom_id.write_date > record.last_update) or
                (record.parent_bom_id and record.parent_bom_id.write_date > record.last_update)
            )

    @api.model
    def _get_dependent_boms(self, bom_id):
        """Obtiene todas las LdM que dependen de la LdM especificada"""
        return self.env['mrp.bom'].search([
            '|',
            ('id', '=', bom_id),
            ('bom_line_ids.product_id.product_tmpl_id.bom_ids', '=', bom_id)
        ])

    @api.depends(
        'bom_id', 'component_id', 'parent_bom_id',
        'bom_id.bom_line_ids.product_qty', 'parent_bom_id.bom_line_ids.product_qty',
        'accumulated_factor'
    )
    def _compute_quantity(self):
        for record in self:
            if not record.bom_id:
                record.quantity = 0.0
                continue

            bom_line = record.bom_id.bom_line_ids.filtered(lambda l: l.product_id == record.component_id)
            record.quantity = (bom_line.product_qty if bom_line else 0.0) * record.accumulated_factor
            record.last_update = fields.Datetime.now()
            _logger.info(f"Cantidad recalculada para {record.component_id.name}: {record.quantity}")

    def update_quantities(self, parent_factor=1.0):
        """Actualiza las cantidades de manera recursiva en cascada"""
        for record in self:
            # Optimización en la actualización del factor acumulado
            if record.parent_bom_id:
                parent_line = record.parent_bom_id.bom_line_ids.filtered(lambda l: l.product_id == record.bom_id.product_tmpl_id.product_variant_id)
                record.accumulated_factor = parent_factor * (parent_line.product_qty if parent_line else 1.0)
            else:
                record.accumulated_factor = parent_factor

            # Actualiza la cantidad para este registro
            record.last_update = fields.Datetime.now()

            # Optimización en la recursión
            self.search([('parent_bom_id', '=', record.bom_id.id)]).update_quantities(record.accumulated_factor)

    def propagate_changes(self):
        """Propaga cambios hacia abajo desde cualquier nivel"""
        all_records = self.search([('bom_id', 'in', self.mapped('bom_id.id'))])
        all_records.filtered(lambda r: not r.parent_bom_id).update_quantities()

    def write(self, vals):
        res = super().write(vals)
        if 'quantity' in vals:  # O cualquier otro campo relevante
            self.propagate_changes()
        return res


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    def write(self, vals):
        """Sobrescribe el método write para manejar actualizaciones"""
        res = super().write(vals)
        if 'bom_line_ids' in vals:
            self._trigger_consolidation_update()
        return res

    def _trigger_consolidation_update(self):
        """Dispara la actualización de los registros de consolidación"""
        consolidation_records = self.env['mrp.bom.tree.consolidation'].search([
            '|',
            ('bom_id', 'in', self.ids),
            ('parent_bom_id', 'in', self.ids)
        ])

        # Optimización en la actualización recursiva
        if consolidation_records:
            consolidation_records.filtered(lambda r: not r.parent_bom_id).update_quantities()

    def analyze_bom(self):
        self.ensure_one()
        _logger.info(f"Iniciando analyze_bom para BOM ID: {self.id}")

        try:
            all_related_boms = set()

            def get_all_bom_ids(bom_id):
                all_related_boms.add(bom_id)
                child_boms = self.env['mrp.bom'].search([('id', '=', bom_id)]).bom_line_ids.mapped('product_id.product_tmpl_id.bom_ids.id')
                for child_bom in child_boms:
                    if child_bom not in all_related_boms:
                        get_all_bom_ids(child_bom)

            get_all_bom_ids(self.id)

            # Limpiar y recrear registros
            consolidation_model = self.env['mrp.bom.tree.consolidation']
            existing_records = consolidation_model.search([
                '|',
                ('bom_id', 'in', list(all_related_boms)),
                ('parent_bom_id', 'in', list(all_related_boms))
            ])
            existing_records.unlink()

            # Procesar la BOM
            all_components = self._recorrer_bom(self)
            created_records = set()

            for component in all_components:
                record_key = (
                    component['bom_id'],
                    component['parent_bom_id'],
                    component['component_id'],
                    component['level']
                )

                if record_key not in created_records:
                    created_records.add(record_key)
                    component['last_update'] = fields.Datetime.now()
                    consolidation_model.create(component)

            # Actualizar cantidades
            root_records = consolidation_model.search([
                ('bom_id', 'in', list(all_related_boms)),
                ('parent_bom_id', '=', False)
            ])
            root_records.update_quantities()

            action = self.env.ref('mrp_bom_tree_consolidation.action_mrp_bom_tree_consolidation').read()[0]
            action.update({
                'domain': [('bom_id', 'in', list(all_related_boms))],
                'context': {
                    'default_bom_id': self.id,
                    'search_default_bom_id': self.id,
                }
            })
            return action

        except Exception as e:
            _logger.error(f"Error en analyze_bom: {str(e)}", exc_info=True)
            raise UserError(f'Error al analizar la lista de materiales: {str(e)}')
