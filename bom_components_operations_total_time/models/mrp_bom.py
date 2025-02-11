from odoo import models, fields, api

class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    total_operation_time_main = fields.Float(
        string='Total operations time (Main)',
        compute='_compute_total_operation_time_main',
        help=(
            'Suma de los tiempos de ciclo manual de las operaciones no archivadas de esta BoM principal, '
            'sin incluir los tiempos de las BoMs hijas. El tiempo se calcula en minutos y segundos.'
        ),
        store=True,
    )

    total_operation_time = fields.Float(
        string='Total operations time',
        compute='_compute_total_operation_time',
        help=(
            'Suma de los tiempos de ciclo manual de las operaciones no archivadas de esta BoM y sus componentes hijos. '
            'El tiempo se calcula en minutos y segundos.'
        ),
        store=True,
    )

    @api.depends('operation_ids.time_cycle_manual', 'operation_ids.active')
    def _compute_total_operation_time_main(self):
        for record in self:
            # Filtrar operaciones activas usando domain
            active_operations = record.operation_ids.filtered(lambda x: x.active)
            total_time = sum(active_operations.mapped('time_cycle_manual'))
            record.total_operation_time_main = total_time

    @api.depends(
        'operation_ids.time_cycle_manual',
        'operation_ids.active',
        'bom_line_ids.product_id.bom_ids.total_operation_time',
        'bom_line_ids.product_id.bom_ids.bom_line_ids.product_id.bom_ids.total_operation_time'
    )
    def _compute_total_operation_time(self):
        for record in self:
            # Filtrar operaciones activas
            active_operations = record.operation_ids.filtered(lambda x: x.active)
            total_time = sum(active_operations.mapped('time_cycle_manual'))

            # Agregar tiempos de las BoMs hijas
            for bom_line in record.bom_line_ids:
                for child_bom in bom_line.product_id.bom_ids:
                    # Solo considerar BoMs activas
                    if child_bom.active:
                        total_time += child_bom.total_operation_time

            record.total_operation_time = total_time

    def action_recompute_total_operation_time(self):
        """Método para forzar la actualización recursiva de tiempos de operación"""
        def recursive_update(boms):
            # Solo considerar BoMs activas
            active_boms = boms.filtered(lambda x: x.active)
            active_boms._compute_total_operation_time()
            active_boms._compute_total_operation_time_main()

            # Buscar y actualizar BoMs hijas
            child_boms = active_boms.mapped('bom_line_ids.product_id.bom_ids')
            if child_boms:
                recursive_update(child_boms)

        recursive_update(self)
        return True