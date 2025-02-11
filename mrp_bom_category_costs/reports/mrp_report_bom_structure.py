import logging
from odoo import models

_logger = logging.getLogger(__name__)


class BomStructureReport(models.AbstractModel):
    _inherit = 'report.mrp.report_bom_structure'
    _description = 'BOM Structure Report'

    def _get_bom_data(self, bom, warehouse, product=False, line_qty=False, level=0, bom_line=False,
                      parent_bom=False, parent_product=False, index=0, product_info=False, ignore_stock=False):
        data = super()._get_bom_data(bom, warehouse, product=product, line_qty=line_qty, level=level,
                                     bom_line=bom_line, parent_bom=parent_bom, parent_product=parent_product,
                                     index=index, product_info=product_info, ignore_stock=ignore_stock)

        # Costos por categoría de producto
        category_costs = {}

        # Obtener la categoría del producto principal
        main_product = product or bom.product_id
        main_category = main_product.categ_id

        if main_category:
            if main_category.id not in category_costs:
                category_costs[main_category.id] = {
                    'name': main_category.name,
                    'material_cost': 0.0,
                    'operation_cost': 0.0,
                    'total_cost': 0.0
                }

        # Calcular costos de operaciones
        if bom.operation_ids:
            for operation in bom.operation_ids:
                workcenter = operation.workcenter_id
                if workcenter:
                    cost = operation.time_cycle_manual * (workcenter.costs_hour / 60.0)
                    if main_category:
                        category_costs[main_category.id]['operation_cost'] += cost
                        category_costs[main_category.id]['total_cost'] += cost

        # Calcular costos de componentes por categoría
        if data.get('components'):
            for component in data['components']:
                if component['type'] == 'component':
                    product = component['product']
                    category = product.categ_id
                    if category:
                        cost = component.get('bom_cost', 0.0) * component.get('quantity', 1.0)
                        if category.id not in category_costs:
                            category_costs[category.id] = {
                                'name': category.name,
                                'material_cost': 0.0,
                                'operation_cost': 0.0,
                                'total_cost': 0.0
                            }
                        category_costs[category.id]['material_cost'] += cost
                        category_costs[category.id]['total_cost'] += cost

                # Recursivamente procesar sub-BOMs
                elif component.get('category_costs'):
                    for cat_cost in component['category_costs']:
                        cat_id = cat_cost.get('id')
                        if cat_id not in category_costs:
                            category_costs[cat_id] = {
                                'name': cat_cost.get('name'),
                                'material_cost': cat_cost.get('material_cost', 0.0),
                                'operation_cost': cat_cost.get('operation_cost', 0.0),
                                'total_cost': cat_cost.get('total_cost', 0.0)
                            }
                        else:
                            category_costs[cat_id]['material_cost'] += cat_cost.get('material_cost', 0.0)
                            category_costs[cat_id]['operation_cost'] += cat_cost.get('operation_cost', 0.0)
                            category_costs[cat_id]['total_cost'] += cat_cost.get('total_cost', 0.0)

        # Convertir el diccionario a lista para el resultado final
        data['category_costs'] = [
            {
                'id': cat_id,
                'name': cat_data['name'],
                'material_cost': cat_data['material_cost'],
                'operation_cost': cat_data['operation_cost'],
                'total_cost': cat_data['total_cost']
            }
            for cat_id, cat_data in category_costs.items()
        ]

        return data