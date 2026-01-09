# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


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
    # OVERRIDE METHODS
    # -------------------------------------------------------------------------
    def button_confirm(self):
        """Override to redirect picking destination to COMEX location."""
        res = super().button_confirm()
        
        for order in self.filtered('comex_operation_id'):
            comex_location = order.comex_operation_id.current_location_id \
                or order.comex_operation_id._get_default_transit_location()
            
            if not comex_location:
                continue
            
            # Find pickings not yet linked to COMEX
            pickings = order.picking_ids.filtered(
                lambda p: p.state not in ('done', 'cancel') and not p.comex_operation_id
            )
            
            for picking in pickings:
                # Update picking destination and COMEX link
                picking.write({
                    'comex_operation_id': order.comex_operation_id.id,
                    'location_dest_id': comex_location.id,
                })
                # Update moves destination AND comex_operation_id (for push rules)
                moves_to_update = picking.move_ids.filtered(
                    lambda m: m.state not in ('done', 'cancel')
                )
                moves_to_update.write({
                    'location_dest_id': comex_location.id,
                    'comex_operation_id': order.comex_operation_id.id,
                })
        
        return res

    def write(self, vals):
        """Sync date_planned to COMEX operation (prevent infinite loop)."""
        res = super().write(vals)
        
        if 'date_planned' in vals and not self.env.context.get('skip_comex_sync'):
            for order in self.filtered('comex_operation_id'):
                if order.date_planned:
                    order.comex_operation_id.with_context(skip_comex_sync=True).write({
                        'date_eta': order.date_planned.date()
                    })
        
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
        """Create a new COMEX operation for this purchase order."""
        self.ensure_one()
        if self.comex_operation_id:
            return self.action_view_comex_operation()
        
        # Create new COMEX operation
        operation = self.env['comex.operation'].create({
            'operation_type': 'import',
            'partner_id': self.partner_id.id,
            'origin_country_id': self.partner_id.country_id.id if self.partner_id.country_id else False,
            'date_eta': self.date_planned.date() if self.date_planned else False,
            'currency_id': self.currency_id.id,
            'amount_fob': self.amount_total,
        })
        
        # Link to purchase order
        self.comex_operation_id = operation.id
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('COMEX Operation'),
            'res_model': 'comex.operation',
            'view_mode': 'form',
            'res_id': operation.id,
        }
