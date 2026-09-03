# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _compute_show_project_and_task_button(self):
        super()._compute_show_project_and_task_button()
        tracked_order_ids = self.env['sale.order.line']._read_group([
            ('order_id', 'in', self.ids),
            ('order_id.state', 'not in', ['draft', 'sent']),
            ('product_id.detailed_type', '!=', 'service'),
            ('product_id.service_tracking', '!=', 'no'),
        ], aggregates=['order_id:array_agg'])[0][0]
        for order in self:
            if order.id not in tracked_order_ids:
                continue
            # Same buttons sale_project shows for real services: reveal them here
            # too once a non-service tracked line generated a project/task.
            order.show_project_button = order.show_project_button or bool(order.project_count)
            order.show_task_button = order.show_task_button or order.show_project_button or bool(order.tasks_count)
