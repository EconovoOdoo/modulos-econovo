# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


class PurchaseOrderLine(models.Model):
    """Extend purchase.order.line to trigger product line sync."""

    _inherit = 'purchase.order.line'

    @api.model_create_multi
    def create(self, vals_list):
        """Trigger product line sync when creating PO lines."""
        lines = super().create(vals_list)
        # Sync product lines for related COMEX operations
        operations = lines.order_id.comex_operation_id
        if operations:
            self.env['comex.operation.product.line'].sudo()._sync_operations(operations)
        return lines

    def write(self, vals):
        """Trigger product line sync when updating PO lines."""
        res = super().write(vals)
        # Only sync if relevant fields changed
        sync_fields = {'product_id', 'product_qty', 'qty_received', 'price_unit', 'name'}
        if sync_fields & set(vals.keys()):
            operations = self.order_id.comex_operation_id
            if operations:
                self.env['comex.operation.product.line'].sudo()._sync_operations(operations)
        return res

    def unlink(self):
        """Trigger product line sync when deleting PO lines."""
        operations = self.order_id.comex_operation_id
        res = super().unlink()
        if operations:
            self.env['comex.operation.product.line'].sudo()._sync_operations(operations)
        return res


class PurchaseOrder(models.Model):
    """Extend purchase.order with COMEX operation link."""

    _inherit = 'purchase.order'

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------
    comex_operation_id = fields.Many2one(
        'comex.operation',
        string="COMEX Operation",
        tracking=True,
        copy=False,
        index=True,
    )
    is_comex = fields.Boolean(
        string="Is COMEX",
        compute='_compute_is_comex',
        store=True,
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    @api.depends('comex_operation_id')
    def _compute_is_comex(self):
        for order in self:
            order.is_comex = bool(order.comex_operation_id)

    # -------------------------------------------------------------------------
    # HELPER METHODS
    # -------------------------------------------------------------------------
    def _link_pickings_to_comex_operation(self):
        """Link all pickings from this PO to its COMEX operation.
        
        Simply assigns comex_operation_id on all pickings (including done/canceled).
        Does NOT modify locations - that's handled manually by stage advancement.
        """
        for order in self:
            if order.comex_operation_id:
                # Link all pickings to the operation (including done/canceled)
                order.picking_ids.write({
                    'comex_operation_id': order.comex_operation_id.id
                })
            else:
                # Unlink pickings when operation is removed
                order.picking_ids.write({
                    'comex_operation_id': False
                })

    # -------------------------------------------------------------------------
    # OVERRIDE METHODS
    # -------------------------------------------------------------------------
    def button_confirm(self):
        """Override to link pickings to COMEX operation and sync product lines."""
        res = super().button_confirm()
        
        # Link newly created pickings to COMEX operation
        self._link_pickings_to_comex_operation()
        
        # Sync product lines after confirmation
        operations = self.filtered('comex_operation_id').comex_operation_id
        if operations:
            self.env['comex.operation.product.line'].sudo()._sync_operations(operations)
        
        return res

    def write(self, vals):
        """Sync date_planned, link/unlink pickings when comex_operation_id changes, and trigger sync on state changes."""
        # Store old operations BEFORE write (for product line sync)
        old_operations = self.mapped('comex_operation_id') if 'comex_operation_id' in vals else self.env['comex.operation']
        
        res = super().write(vals)
        
        if 'date_planned' in vals and not self.env.context.get('skip_comex_sync'):
            for order in self.filtered('comex_operation_id'):
                if order.date_planned:
                    order.comex_operation_id.with_context(skip_comex_sync=True).write({
                        'date_eta': order.date_planned.date()
                    })
        
        # Link/unlink pickings when comex_operation_id changes (assigned or removed)
        if 'comex_operation_id' in vals:
            self._link_pickings_to_comex_operation()
            # Sync product lines for both old and new operations
            new_operations = self.mapped('comex_operation_id')
            all_operations = old_operations | new_operations
            if all_operations:
                self.env['comex.operation.product.line'].sudo()._sync_operations(all_operations)
        
        # Sync product lines when PO state changes
        if 'state' in vals:
            operations = self.filtered('comex_operation_id').comex_operation_id
            if operations:
                self.env['comex.operation.product.line'].sudo()._sync_operations(operations)
        
        return res

    # -------------------------------------------------------------------------
    # ACTION METHODS
    # -------------------------------------------------------------------------
    def action_view_comex_operation(self):
        """Open related COMEX operation."""
        self.ensure_one()
        if not self.comex_operation_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('COMEX Operation'),
            'res_model': 'comex.operation',
            'view_mode': 'form',
            'res_id': self.comex_operation_id.id,
        }

    def action_create_comex_operation(self):
        """Create a new COMEX operation for this purchase order and link existing pickings."""
        self.ensure_one()
        if self.comex_operation_id:
            return self.action_view_comex_operation()
        
        # Create new COMEX operation (stage will be assigned by default via model)
        operation = self.env['comex.operation'].create({
            'operation_type': 'import',
            'partner_id': self.partner_id.id,
            'origin_country_id': self.partner_id.country_id.id if self.partner_id.country_id else False,
            'date_eta': self.date_planned.date() if self.date_planned else False,
            'currency_id': self.currency_id.id,
            'amount_fob': self.amount_total,
        })
        
        # Link to purchase order (this will trigger _link_pickings_to_comex_operation via write)
        self.comex_operation_id = operation.id
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('COMEX Operation'),
            'res_model': 'comex.operation',
            'view_mode': 'form',
            'res_id': operation.id,
        }
