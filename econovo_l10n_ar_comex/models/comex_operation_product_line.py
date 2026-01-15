# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

import logging
from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class ComexOperationProductLine(models.Model):
    """Product lines for COMEX operations.
    
    This model provides a unified view of all products associated with COMEX operations,
    whether they come from purchase orders (imports) or sale orders (exports).
    
    Follows OCA purchase_request pattern: separate line model for better filtering,
    grouping, and reporting capabilities.
    """
    
    _name = 'comex.operation.product.line'
    _description = 'COMEX Operation Product Line'
    _order = 'operation_id, sequence, id'

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------
    # Header relation
    operation_id = fields.Many2one(
        'comex.operation',
        string="COMEX Operation",
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
    )
    company_id = fields.Many2one(
        'res.company',
        string="Company",
        related='operation_id.company_id',
        store=True,
    )
    
    # Product information
    product_id = fields.Many2one(
        'product.product',
        string="Product",
        required=True,
        index=True,
    )
    product_tmpl_id = fields.Many2one(
        'product.template',
        string="Product Template",
        related='product_id.product_tmpl_id',
        store=True,
    )
    name = fields.Text(
        string="Description",
        required=True,
    )
    
    # Quantities
    product_qty = fields.Float(
        string="Quantity",
        required=True,
        digits='Product Unit of Measure',
    )
    product_uom = fields.Many2one(
        'uom.uom',
        string="Unit of Measure",
        required=True,
    )
    qty_received = fields.Float(
        string="Received Qty",
        digits='Product Unit of Measure',
        readonly=True,
        help="Received quantity (for imports)",
    )
    qty_delivered = fields.Float(
        string="Delivered Qty",
        digits='Product Unit of Measure',
        readonly=True,
        help="Delivered quantity (for exports)",
    )
    
    # Pricing
    currency_id = fields.Many2one(
        'res.currency',
        string="Currency",
        related='operation_id.currency_id',
        store=True,
    )
    price_unit = fields.Float(
        string="Unit Price",
        required=True,
        digits='Product Price',
    )
    price_subtotal = fields.Monetary(
        string="Subtotal",
        compute='_compute_price_subtotal',
        store=True,
        currency_field='currency_id',
    )
    
    # Origin tracking
    origin_type = fields.Selection(
        selection=[
            ('purchase', 'Purchase Order'),
            ('sale', 'Sale Order'),
            ('manual', 'Manual Entry'),
        ],
        string="Origin",
        required=True,
        default='manual',
    )
    purchase_line_id = fields.Many2one(
        'purchase.order.line',
        string="Purchase Order Line",
        ondelete='set null',
        index=True,
    )
    sale_line_id = fields.Many2one(
        'sale.order.line',
        string="Sale Order Line",
        ondelete='set null',
        index=True,
    )
    
    # Related orders (for navigation and filtering)
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string="Purchase Order",
        related='purchase_line_id.order_id',
        store=True,
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string="Sale Order",
        related='sale_line_id.order_id',
        store=True,
    )
    
    # Container tracking (via quants)
    package_id = fields.Many2one(
        'stock.quant.package',
        string="Container",
        compute='_compute_package_id',
        store=False,
        help="Container that contains this product (computed from stock quants)",
    )
    container_number = fields.Char(
        string="Container Number",
        related='package_id.comex_container_number',
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    @api.depends('product_qty', 'price_unit')
    def _compute_price_subtotal(self):
        """Calculate subtotal as quantity * unit price."""
        for line in self:
            line.price_subtotal = line.product_qty * line.price_unit

    def _compute_package_id(self):
        """Find which container has this product (via stock.quant)."""
        for line in self:
            if not line.product_id or not line.operation_id:
                line.package_id = False
                continue
            
            # Search for quant in operation's shipment containers
            quant = self.env['stock.quant'].search([
                ('product_id', '=', line.product_id.id),
                ('package_id.comex_operation_id', '=', line.operation_id.id),
                ('quantity', '>', 0),
            ], limit=1)
            
            line.package_id = quant.package_id if quant else False

    # -------------------------------------------------------------------------
    # ONCHANGE METHODS
    # -------------------------------------------------------------------------
    @api.onchange('product_id')
    def _onchange_product_id(self):
        """Auto-fill product information when product is selected."""
        if self.product_id:
            self.name = self.product_id.display_name
            self.product_uom = self.product_id.uom_id
            # Set default price from product if available
            if self.product_id.list_price:
                self.price_unit = self.product_id.list_price

    # -------------------------------------------------------------------------
    # CRUD METHODS
    # -------------------------------------------------------------------------
    @api.model
    def web_search_read(self, domain=None, specification=None, offset=0, limit=None, order=None, count_limit=None):
        """Override web_search_read to auto-sync before displaying in views.
        
        This is the method actually called by Odoo web client when loading list views.
        """
        # Prevent infinite recursion during sync
        if not self.env.context.get('skip_product_line_sync'):
            _logger.info("=== PRODUCT LINES WEB_SEARCH_READ CALLED ===")
            _logger.info(f"Domain: {domain}")
            
            # Trigger synchronization for all operations (with context flag)
            self.with_context(skip_product_line_sync=True)._sync_all_operations()
        
        # Call parent method
        result = super().web_search_read(domain=domain, specification=specification, offset=offset, 
                                        limit=limit, order=order, count_limit=count_limit)
        
        # Log result
        if not self.env.context.get('skip_product_line_sync'):
            record_count = result.get('length', 0) if isinstance(result, dict) else 0
            _logger.info(f"web_search_read returned {record_count} records")
        
        return result
    
    @api.model
    def search(self, domain, offset=0, limit=None, order=None, count=False):
        """Override search to auto-sync product lines before displaying results.
        
        This ensures that when accessing the Product Lines view directly,
        all PO/SO lines are synchronized before showing the list.
        """
        # Prevent infinite recursion during sync
        if not self.env.context.get('skip_product_line_sync'):
            _logger.info("=== PRODUCT LINES SEARCH CALLED ===")
            _logger.info(f"Domain: {domain}")
            
            # Trigger synchronization for all operations (with context flag)
            self.with_context(skip_product_line_sync=True)._sync_all_operations()
        
        # Execute normal search (count parameter is handled by search_count method)
        if count:
            result = super().search_count(domain)
        else:
            result = super().search(domain, offset=offset, limit=limit, order=order)
        _logger.info(f"Search result count: {len(result) if not count else result}")
        
        return result

    @api.model
    def _sync_operations(self, operations):
        """Synchronize product lines for specific COMEX operations.
        
        Args:
            operations: comex.operation recordset
        """
        for operation in operations:
            self._sync_operation(operation)

    @api.model
    def _sync_all_operations(self):
        """Synchronize product lines for all COMEX operations.
        
        This method is called automatically before each search to ensure
        the view always shows up-to-date data from PO/SO lines.
        """
        _logger.info("=== Starting sync for all operations ===")
        
        # Get all operations with purchase orders
        operations = self.env['comex.operation'].search([
            ('purchase_order_ids', '!=', False)
        ])
        
        _logger.info(f"Found {len(operations)} operations with purchase orders")
        
        self._sync_operations(operations)

    @api.model
    def _sync_operation(self, operation):
        """Synchronize product lines for a single operation.
        
        Args:
            operation: comex.operation recordset
        """
        _logger.info(f"Syncing operation {operation.name} (ID: {operation.id})")
        
        # Get existing product lines for this operation (skip sync to avoid recursion)
        existing_lines = self.with_context(skip_product_line_sync=True).search([
            ('operation_id', '=', operation.id)
        ])
        _logger.info(f"  Existing lines: {len(existing_lines)}")
        
        existing_po_lines = {line.purchase_line_id.id: line for line in existing_lines if line.purchase_line_id}
        
        # Get all PO lines from operation's purchase orders (only confirmed POs with active comex link)
        confirmed_pos = operation.purchase_order_ids.filtered(
            lambda po: po.state in ['purchase', 'done'] and po.comex_operation_id == operation
        )
        current_po_lines = confirmed_pos.mapped('order_line')
        _logger.info(f"  Current PO lines: {len(current_po_lines)} from {len(confirmed_pos)} confirmed POs")
        
        current_po_line_ids = set(current_po_lines.ids)
        
        # Lines to create (new PO lines not in database)
        lines_to_create = []
        for po_line in current_po_lines:
            if po_line.id not in existing_po_lines:
                lines_to_create.append({
                    'operation_id': operation.id,
                    'product_id': po_line.product_id.id,
                    'name': po_line.name,
                    'product_qty': po_line.product_qty,
                    'product_uom': po_line.product_uom.id,
                    'price_unit': po_line.price_unit,
                    'qty_received': po_line.qty_received,
                    'origin_type': 'purchase',
                    'purchase_line_id': po_line.id,
                })
        
        # Create new lines (use sudo for automated sync)
        if lines_to_create:
            _logger.info(f"  Creating {len(lines_to_create)} new product lines")
            self.sudo().create(lines_to_create)
        
        # Update existing lines with latest data (use sudo for automated sync)
        updates = 0
        for po_line in current_po_lines:
            if po_line.id in existing_po_lines:
                existing_po_lines[po_line.id].sudo().write({
                    'product_qty': po_line.product_qty,
                    'qty_received': po_line.qty_received,
                    'price_unit': po_line.price_unit,
                })
                updates += 1
        
        if updates > 0:
            _logger.info(f"  Updated {updates} existing lines")
        
        # Delete obsolete lines (PO lines that no longer exist, use sudo for automated sync)
        lines_to_delete = existing_lines.filtered(
            lambda l: l.purchase_line_id and l.purchase_line_id.id not in current_po_line_ids
        )
        if lines_to_delete:
            _logger.info(f"  Deleting {len(lines_to_delete)} obsolete lines")
            lines_to_delete.sudo().unlink()

    @api.model_create_multi
    def create(self, vals_list):
        """Ensure product name is set on creation."""
        for vals in vals_list:
            if vals.get('product_id') and not vals.get('name'):
                product = self.env['product.product'].browse(vals['product_id'])
                vals['name'] = product.display_name
        return super().create(vals_list)

    # -------------------------------------------------------------------------
    # ACTION METHODS
    # -------------------------------------------------------------------------
    def action_view_purchase_order(self):
        """Open related purchase order."""
        self.ensure_one()
        if not self.purchase_order_id:
            return False
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Order'),
            'res_model': 'purchase.order',
            'res_id': self.purchase_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_sale_order(self):
        """Open related sale order."""
        self.ensure_one()
        if not self.sale_order_id:
            return False
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sale Order'),
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_container(self):
        """Open related container (package)."""
        self.ensure_one()
        # Force recompute to get latest package
        self._compute_package_id()
        
        if not self.package_id:
            return False
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Container'),
            'res_model': 'stock.quant.package',
            'res_id': self.package_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
