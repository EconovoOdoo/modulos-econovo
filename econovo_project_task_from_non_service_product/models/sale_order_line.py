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
