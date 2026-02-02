# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class SaleOrder(models.Model):
    """Extend sale.order to link with COMEX operations."""

    _inherit = 'sale.order'

    comex_operation_id = fields.Many2one(
        'comex.operation',
        string="COMEX Operation",
        tracking=True,
        domain="[('operation_type', '=', 'export')]",
        help="COMEX export operation associated with this sales order.",
    )
    is_comex = fields.Boolean(
        string="Is COMEX",
        compute='_compute_is_comex',
        store=True,
        help="Indicates if this sales order is linked to a COMEX operation.",
    )

    @api.depends('comex_operation_id')
    def _compute_is_comex(self):
        """Compute if this sales order is linked to a COMEX operation."""
        for order in self:
            order.is_comex = bool(order.comex_operation_id)

    def _link_pickings_to_comex_operation(self):
        """Link/unlink all pickings (deliveries) to comex_operation_id when it changes.
        
        Simply assigns comex_operation_id on all pickings (including done/canceled).
        Sync is done at the COMEX operation level when syncing dates or products.
        """
        for order in self:
            if order.comex_operation_id:
                # Link all pickings to operation
                order.picking_ids.write({
                    'comex_operation_id': order.comex_operation_id.id
                })
            else:
                # Unlink all pickings from operation
                order.picking_ids.write({
                    'comex_operation_id': False
                })

    @api.model_create_multi
    def create(self, vals_list):
        """Override to link pickings and trigger COMEX sync on creation."""
        orders = super().create(vals_list)
        
        # Link pickings to COMEX operation
        orders._link_pickings_to_comex_operation()
        
        # Trigger COMEX sync for operations
        operations = orders.filtered('comex_operation_id').comex_operation_id
        if operations:
            self.env['comex.operation.product.line'].sudo()._sync_operations(operations)
        
        return orders

    def write(self, vals):
        """Sync date_planned, link/unlink pickings when comex_operation_id changes, and trigger sync on state changes."""
        # Store old operations before write
        old_operations = self.mapped('comex_operation_id') if 'comex_operation_id' in vals else self.env['comex.operation']
        
        result = super().write(vals)
        
        # Sync date_planned to operation date_eta if comex_operation_id is set
        if 'commitment_date' in vals:
            for order in self.filtered('comex_operation_id'):
                if order.commitment_date:
                    order.comex_operation_id.with_context(skip_comex_sync=True).write({
                        'date_eta': order.commitment_date
                    })
        
        # Link/unlink pickings when comex_operation_id changes (assigned or removed)
        if 'comex_operation_id' in vals:
            self._link_pickings_to_comex_operation()
        
        # Trigger COMEX sync on relevant changes
        if any(key in vals for key in ['state', 'order_line', 'comex_operation_id']):
            # Sync old operations (in case order was removed from operation)
            if old_operations:
                self.env['comex.operation.product.line'].sudo()._sync_operations(old_operations)
            
            # Sync new operations
            new_operations = self.filtered('comex_operation_id').comex_operation_id
            if new_operations:
                self.env['comex.operation.product.line'].sudo()._sync_operations(new_operations)
        
        return result

    def action_view_comex_operation(self):
        """Open the related COMEX operation."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'COMEX Operation',
            'res_model': 'comex.operation',
            'res_id': self.comex_operation_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_create_comex_operation(self):
        """Create a new COMEX operation from this sales order."""
        self.ensure_one()
        
        # Prepare values for new COMEX operation
        operation_vals = {
            'operation_type': 'export',
            'partner_id': self.partner_id.id,
            'date_operation': fields.Date.context_today(self),
            'date_eta': self.commitment_date,
            'currency_id': self.currency_id.id,
        }
        
        # Create operation
        operation = self.env['comex.operation'].create(operation_vals)
        
        # Link this SO to the operation
        self.write({'comex_operation_id': operation.id})
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'COMEX Operation',
            'res_model': 'comex.operation',
            'res_id': operation.id,
            'view_mode': 'form',
            'target': 'current',
        }
