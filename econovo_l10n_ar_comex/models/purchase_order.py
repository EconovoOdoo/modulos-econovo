# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class PurchaseOrderLine(models.Model):
    """Extend purchase.order.line to trigger product line sync."""

    _inherit = 'purchase.order.line'

    @api.model_create_multi
    def create(self, vals_list):
        """Trigger product line sync when creating PO lines."""
        lines = super().create(vals_list)
        # Sync product lines for related COMEX operations
        operations = lines.order_id.sudo().comex_operation_id
        if operations:
            self.env['comex.operation.product.line'].sudo()._sync_operations(operations)
        return lines

    def write(self, vals):
        """Trigger product line sync when updating PO lines."""
        res = super().write(vals)
        # Only sync if relevant fields changed
        sync_fields = {'product_id', 'product_qty', 'qty_received', 'price_unit', 'name'}
        if sync_fields & set(vals.keys()):
            operations = self.order_id.sudo().comex_operation_id
            if operations:
                self.env['comex.operation.product.line'].sudo()._sync_operations(operations)
        return res

    def unlink(self):
        """Trigger product line sync when deleting PO lines."""
        operations = self.order_id.sudo().comex_operation_id
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
        domain="[('operation_type', '=', 'import')]",
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
    # ONCHANGE METHODS
    # -------------------------------------------------------------------------
    @api.onchange('comex_operation_id')
    def _onchange_comex_operation_id(self):
        """Set COMEX picking type when linking a draft PO to an import operation.

        Uses the per-company default COMEX import picking type configured in
        Settings > COMEX. Falls back to COMEX/IN if no default is set.
        """
        if not self.comex_operation_id:
            return
        if self.comex_operation_id.operation_type != 'import':
            return
        if self.state != 'draft':
            return

        comex_pt = self.company_id._get_comex_default_import_picking_type()
        if comex_pt:
            self.picking_type_id = comex_pt

    # -------------------------------------------------------------------------
    # HELPER METHODS
    # -------------------------------------------------------------------------
    def _get_all_chained_pickings(self):
        """Follow the move chain (move_dest_ids) to find ALL related pickings.

        purchase.order.picking_ids only contains pickings whose moves are
        directly linked to PO lines.  Push-rule-generated pickings (e.g.
        COMEX/ARR, COMEX/FIS, COMEX/NAC) are created for chained moves that
        are NOT linked to PO lines, so they are missing from picking_ids.

        This method starts from the PO-line moves and recursively follows
        move_dest_ids to collect every picking in the chain.

        Returns:
            tuple(stock.picking recordset, stock.move recordset)
        """
        self.ensure_one()
        all_moves = self.order_line.move_ids
        all_pickings = all_moves.picking_id

        # Walk the move chain forward
        moves_to_check = all_moves
        while moves_to_check:
            next_moves = moves_to_check.mapped('move_dest_ids') - all_moves
            if not next_moves:
                break
            all_moves |= next_moves
            all_pickings |= next_moves.picking_id
            moves_to_check = next_moves

        return all_pickings, all_moves

    def _link_pickings_to_comex_operation(self):
        """Link all pickings from this PO to its COMEX operation.

        Follows the move_dest_ids chain so that push-rule-generated pickings
        (En Viaje -> En Puerto -> Deposito Fiscal -> Stock) are also linked.
        Sets comex_operation_id on both pickings AND moves so that future
        push-rule propagation (_push_prepare_move_copy_values) works even
        if new chain steps are added later.

        Does NOT modify locations - that is handled by stage advancement.
        Uses sudo() because COMEX fields have groups= restriction.
        """
        for order in self.sudo():
            all_pickings, all_moves = order._get_all_chained_pickings()
            if order.comex_operation_id:
                op_id = order.comex_operation_id.id
                # Update pickings that don't yet have the correct operation
                pickings_to_update = all_pickings.filtered(
                    lambda p: p.comex_operation_id.id != op_id
                )
                if pickings_to_update:
                    pickings_to_update.write({'comex_operation_id': op_id})
                # Update moves so push-rule copy() propagates the value
                moves_to_update = all_moves.filtered(
                    lambda m: m.comex_operation_id.id != op_id
                )
                if moves_to_update:
                    moves_to_update.write({'comex_operation_id': op_id})
            else:
                # Unlink pickings/moves when operation is removed
                pickings_to_clear = all_pickings.filtered('comex_operation_id')
                if pickings_to_clear:
                    pickings_to_clear.write({'comex_operation_id': False})
                moves_to_clear = all_moves.filtered('comex_operation_id')
                if moves_to_clear:
                    moves_to_clear.write({'comex_operation_id': False})

    # -------------------------------------------------------------------------
    # OVERRIDE METHODS
    # -------------------------------------------------------------------------
    def button_confirm(self):
        """Override to link pickings to COMEX operation and sync product lines."""
        res = super().button_confirm()
        
        # Link newly created pickings to COMEX operation
        self._link_pickings_to_comex_operation()
        
        # Sync product lines after confirmation
        operations = self.sudo().filtered('comex_operation_id').comex_operation_id
        if operations:
            self.env['comex.operation.product.line'].sudo()._sync_operations(operations)
        
        return res

    def write(self, vals):
        """Sync date_planned, link/unlink pickings when comex_operation_id changes, and trigger sync on state changes."""
        # Store old operations BEFORE write (for product line sync)
        old_operations = self.sudo().mapped('comex_operation_id') if 'comex_operation_id' in vals else self.env['comex.operation']
        
        # Prevent reassigning comex_operation_id if pickings are already done
        if 'comex_operation_id' in vals:
            for order in self.sudo():
                if order.comex_operation_id and order.comex_operation_id.id != vals['comex_operation_id']:
                    done_pickings = order.picking_ids.filtered(
                        lambda p: p.state == 'done' and p.comex_operation_id
                    )
                    if done_pickings:
                        raise UserError(_(
                            "Cannot change COMEX operation for '%(order)s' because "
                            "it has validated transfers linked to the current operation:\n"
                            "%(pickings)s",
                            order=order.name,
                            pickings='\n'.join(done_pickings.mapped('name')),
                        ))
        
        res = super().write(vals)
        
        if 'date_planned' in vals and not self.env.context.get('skip_comex_sync'):
            for order in self.sudo().filtered('comex_operation_id'):
                if order.date_planned:
                    order.comex_operation_id.with_context(skip_comex_sync=True).write({
                        'date_eta': order.date_planned.date()
                    })
        
        # Link/unlink pickings when comex_operation_id changes (assigned or removed)
        if 'comex_operation_id' in vals:
            self._link_pickings_to_comex_operation()
            # Sync product lines for both old and new operations
            new_operations = self.sudo().mapped('comex_operation_id')
            all_operations = old_operations | new_operations
            if all_operations:
                self.env['comex.operation.product.line'].sudo()._sync_operations(all_operations)
        
        # Sync product lines when PO state changes
        if 'state' in vals:
            operations = self.sudo().filtered('comex_operation_id').comex_operation_id
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
            'destination_country_id': self.company_id.country_id.id if self.company_id.country_id else False,
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
