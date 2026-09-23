# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0).
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Replace the per-warehouse resupply route by the global one on existing chains.

    Until 17.0.1.1.0 the assistant wrote ``stock.warehouse.subcontracting_route_id`` on the
    components. That route is created with ``product_selectable=False``, so it is meaningless
    on a product and invisible in ``product.template.route_ids``, which left every chain
    permanently flagged as missing its route.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    chains = env['mrp.subcontracting.chain'].with_context(active_test=False).search([])
    if not chains:
        return
    # Only what actually travels to the subcontractor, never the in-house components.
    products = (
        chains.component_line_ids.product_tmpl_id | chains.phantom_product_tmpl_ids
    ).with_context(active_test=False)
    global_route = env['mrp.subcontracting.chain']._get_resupply_route()
    warehouse_routes = env['stock.warehouse'].with_context(active_test=False).search(
        []).subcontracting_route_id
    for product in products:
        commands = [(3, route.id) for route in warehouse_routes]
        if global_route:
            commands.append((4, global_route.id))
        product.write({'route_ids': commands})
