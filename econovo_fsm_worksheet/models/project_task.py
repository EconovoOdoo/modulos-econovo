# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProjectTask(models.Model):
    """Adds the equipment (lot_id) field to FSM tasks.

    The technician selects the equipment number/serial from their task.
    This field is mirrored as a stored related (x_lot_id) on the worksheet
    model to enable group-by in the Analysis view.

    Also provides computed fields derived from the linked sale order and its
    delivery pickings/invoices, so the worksheet can display them automatically
    without requiring manual input from the technician.
    """

    _inherit = 'project.task'

    lot_id = fields.Many2one(
        'stock.lot',
        string='Equipo (N/S)',
        help='Número de serie / equipo al que se realiza el servicio técnico.',
    )

    # --- SO-derived fields (read from sale_line_id.order_id) ---

    so_name = fields.Char(
        related='sale_line_id.order_id.name',
        string='Orden de Venta',
    )
    so_client_order_ref = fields.Char(
        related='sale_line_id.order_id.client_order_ref',
        string='OC Cliente',
    )
    so_invoice_name = fields.Char(
        compute='_compute_so_invoice_name',
        string='Nro Factura',
    )
    so_remito_voucher = fields.Char(
        compute='_compute_so_remito_voucher',
        string='Nro Remito',
    )

    @api.depends('sale_line_id.order_id.invoice_ids.state', 'sale_line_id.order_id.invoice_ids.name')
    def _compute_so_invoice_name(self):
        for task in self:
            order = task.sale_line_id.order_id
            if order:
                invoices = order.invoice_ids.filtered(
                    lambda i: i.state == 'posted' and i.move_type == 'out_invoice'
                )
                task.so_invoice_name = ', '.join(i.name for i in invoices if i.name)
            else:
                task.so_invoice_name = ''

    @api.depends(
        'sale_line_id.order_id.picking_ids',
        'sale_line_id.order_id.picking_ids.state',
        'sale_line_id.order_id.picking_ids.picking_type_code',
    )
    def _compute_so_remito_voucher(self):
        """Compute remito numbers from outgoing done pickings.

        Uses getattr to safely access the 'vouchers' field from stock_voucher
        (ingadhoc) when installed, without requiring it as a hard dependency.
        """
        for task in self:
            order = task.sale_line_id.order_id
            if order:
                pickings = order.picking_ids.filtered(
                    lambda p: p.picking_type_code == 'outgoing' and p.state == 'done'
                )
                task.so_remito_voucher = ', '.join(
                    getattr(p, 'vouchers', '') for p in pickings
                    if getattr(p, 'vouchers', '')
                )
            else:
                task.so_remito_voucher = ''
