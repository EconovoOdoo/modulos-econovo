# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.depends('product_id.service_tracking')
    def _compute_is_service(self):
        super()._compute_is_service()
        for line in self:
            if not line.is_service and line.product_id.service_tracking != 'no':
                # Let non-service (consumable/storable) products configured with a
                # Service Tracking value go through the same project/task generation
                # pipeline as real services (sale_project keys everything off is_service).
                line.is_service = True

    @api.depends('product_id.type', 'product_id.service_tracking')
    def _compute_qty_delivered_method(self):
        super()._compute_qty_delivered_method()
        for line in self:
            if not line.is_expense and line.product_id.type != 'service' \
                    and line.product_id.service_tracking != 'no':
                # sale_stock unconditionally forces 'stock_move' for every
                # consu/product-typed line, tracked or not. A tracked line is
                # already routed through the full sale_project pipeline like a
                # real service (see _compute_is_service above): keep it on
                # 'manual' too, exactly like a real service, instead of also
                # wiring it to the stock-move delivery mechanism it doesn't
                # need (invoicing here is order-based, not delivery-based).
                line.qty_delivered_method = 'manual'

    @api.depends('product_id.service_tracking')
    def _compute_product_updatable(self):
        super()._compute_product_updatable()
        for line in self:
            if line.product_updatable and line.state == 'sale' \
                    and line.product_id.type != 'service' \
                    and line.product_id.service_tracking != 'no':
                # Mirror sale_project's own lock for real services: once a project/task
                # has been generated, the product can no longer be swapped on the line.
                line.product_updatable = False
