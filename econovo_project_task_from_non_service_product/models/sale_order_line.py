# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models
from odoo.tools import float_is_zero

from odoo.addons.industry_fsm_sale.models.sale_order import SaleOrderLine as FsmSaleOrderLine


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

    # --- Field Service (industry_fsm_sale) interaction -----------------------
    #
    # WHY THIS EXISTS (keep when upgrading Odoo -- re-check industry_fsm_sale):
    # `industry_fsm_sale` forces `qty_to_invoice = 0` (and, once Odoo fixes the
    # typo noted below, `invoice_status = 'no'`) on EVERY zero-priced line linked
    # to a Field Service task, so that free materials consumed during an
    # intervention never reach the customer invoice. That guard cannot tell apart
    # the two very different kinds of line it catches:
    #   1. materials added from inside the FSM task  -> guard is correct, keep it;
    #   2. the Sales Order line that GENERATED the task -> guard is wrong here.
    # This module creates case 2 for non-service products, and the business bills
    # warranty labour at 0 on purpose, so those lines must still reach the invoice.
    # `sale.order._get_invoiceable_lines()` skips anything whose `qty_to_invoice`
    # is zero, so without this override the line silently vanishes from the invoice.
    #
    # The two cases are told apart by `task_id.sale_line_id`: it points back to the
    # line that generated the task, and is empty on manually created FSM tasks.
    #
    # `super(FsmSaleOrderLine, ...)` deliberately resumes the MRO right AFTER
    # industry_fsm_sale, so only its guard is skipped and every other override
    # (core `sale` included) still runs for these lines.

    def _get_fsm_warranty_service_lines(self):
        """Lines that generated their own Field Service task and are billed at 0."""
        return self.filtered(
            lambda sol: sol.task_id.is_fsm
            and sol.task_id.sale_line_id == sol
            and float_is_zero(sol.price_unit, precision_rounding=sol.currency_id.rounding)
        )

    @api.depends('task_id.is_fsm', 'task_id.sale_line_id')
    def _compute_qty_to_invoice(self):
        warranty_lines = self._get_fsm_warranty_service_lines()
        super(SaleOrderLine, self - warranty_lines)._compute_qty_to_invoice()
        super(FsmSaleOrderLine, warranty_lines)._compute_qty_to_invoice()

    @api.depends('task_id.is_fsm', 'task_id.sale_line_id')
    def _compute_invoice_status(self):
        # Defensive symmetry only: industry_fsm_sale's own override filters on
        # `invoice_status in (None, 'to_invoice')`, but the real selection value is
        # 'to invoice' (with a space), so today that branch is dead code. Kept so the
        # status stays consistent if Odoo ever fixes that typo upstream.
        warranty_lines = self._get_fsm_warranty_service_lines()
        super(SaleOrderLine, self - warranty_lines)._compute_invoice_status()
        super(FsmSaleOrderLine, warranty_lines)._compute_invoice_status()
