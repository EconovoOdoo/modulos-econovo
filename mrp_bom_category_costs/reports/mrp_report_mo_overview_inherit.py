from odoo import models, api
from collections import defaultdict


class MrpReportMoOverviewInherit(models.AbstractModel):
    _inherit = 'report.mrp.report_mo_overview'

    def _get_report_data(self, production_id):
        # Llamar al método original para obtener los datos base
        result = super()._get_report_data(production_id)

        # Agregar los costos por categoría
        result['category_costs'] = self._get_category_costs(result.get('components', []), result.get('extras', {}))

        return result

    def _get_category_costs(self, components, extra_lines):
        """
        Calcular costos totales agrupados por categoría de producto
        """
        category_costs = defaultdict(lambda: {
            'total_mo_cost_components': 0,
            'total_real_cost_components': 0,
            'products': set(),
            'component_count': 0
        })

        for component in components:
            summary = component.get('summary', {})
            product = self.env['product.product'].browse(summary.get('product_id'))

            if product and product.categ_id:
                category_name = product.categ_id.name
                category_costs[category_name]['products'].add(summary.get('name', ''))
                category_costs[category_name]['total_mo_cost_components'] += summary.get('mo_cost', 0)
                category_costs[category_name]['total_real_cost_components'] += summary.get('real_cost', 0)
                category_costs[category_name]['component_count'] += 1

        # Convertir conjunto de productos a lista para serialización
        for category in category_costs.values():
            category['products'] = list(category['products'])

        return dict(category_costs)