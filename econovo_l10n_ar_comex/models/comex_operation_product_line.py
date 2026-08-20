# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

import logging
from odoo import _, api, fields, models
from odoo.tools import float_compare

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

    _sql_constraints = [
        ('purchase_line_uniq', 'unique(purchase_line_id)',
         'A purchase order line can only be linked to one COMEX product line.'),
        ('sale_line_uniq', 'unique(sale_line_id)',
         'A sale order line can only be linked to one COMEX product line.'),
    ]

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
        search='_search_package_id',
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

    def _search_package_id(self, operator, value):
        """Search method for package_id computed field.
        
        This allows filtering by container/package in list views.
        """
        # Search for quants with the matching package
        quants = self.env['stock.quant'].search([
            ('package_id', operator, value),
        ])
        
        # Get unique product IDs from those quants
        product_ids = quants.mapped('product_id').ids
        
        # Return domain matching lines with those products in this operation
        return [('product_id', 'in', product_ids)]

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
    @api.model_create_multi
    def create(self, vals_list):
        """Ensure product name is set on creation."""
        for vals in vals_list:
            if vals.get('product_id') and not vals.get('name'):
                product = self.env['product.product'].browse(vals['product_id'])
                vals['name'] = product.display_name
        return super().create(vals_list)

    # -------------------------------------------------------------------------
    # SYNCHRONIZATION METHODS
    # -------------------------------------------------------------------------
    @api.model
    def _sync_operations(self, operations):
        """Reconcile the product lines of the given COMEX operations.

        Entry point used by the purchase/sale order triggers and by the daily
        cron. Synchronisation is never triggered by a read operation.
        """
        if self.env.context.get('comex_skip_line_sync'):
            return
        product_lines = self.sudo().with_context(comex_skip_line_sync=True)
        for operation in operations:
            product_lines._sync_operation(operation)

    @api.model
    def _sync_operation(self, operation):
        """Reconcile the product lines of a single COMEX operation."""
        source_values = self._prepare_sync_values(operation)

        existing_lines = self.search([
            ('operation_id', '=', operation.id),
            ('origin_type', 'in', ('purchase', 'sale')),
        ])
        existing_by_key = {line._get_sync_key(): line for line in existing_lines}

        obsolete_keys = set(existing_by_key) - set(source_values)
        if obsolete_keys:
            obsolete_lines = self.browse([existing_by_key[key].id for key in obsolete_keys])
            _logger.info(
                "COMEX %s: removing %s obsolete product lines",
                operation.name, len(obsolete_lines),
            )
            obsolete_lines.unlink()

        lines_to_create = []
        for key, values in source_values.items():
            line = existing_by_key.get(key)
            if line:
                line._write_sync_values(values)
            else:
                lines_to_create.append(dict(values, operation_id=operation.id))

        if lines_to_create:
            _logger.info(
                "COMEX %s: creating %s product lines",
                operation.name, len(lines_to_create),
            )
            self.create(lines_to_create)

    @api.model
    def _prepare_sync_values(self, operation):
        """Build the expected product lines of an operation, keyed by source.

        Override to add new line sources. The key must uniquely identify the
        origin record so lines can be matched, updated and removed.
        """
        source_values = self._prepare_purchase_sync_values(operation)
        source_values.update(self._prepare_sale_sync_values(operation))
        return source_values

    @api.model
    def _prepare_purchase_sync_values(self, operation):
        """Expected product lines coming from the operation purchase orders."""
        orders = operation.purchase_order_ids.filtered(
            lambda order: order.state in self._get_purchase_sync_states()
            and order.comex_operation_id == operation
        )
        return {
            ('purchase', order_line.id): {
                'product_id': order_line.product_id.id,
                'name': order_line.name,
                'product_qty': order_line.product_qty,
                'product_uom': order_line.product_uom.id,
                'price_unit': order_line.price_unit,
                'qty_received': order_line.qty_received,
                'qty_delivered': 0.0,
                'origin_type': 'purchase',
                'purchase_line_id': order_line.id,
                'sale_line_id': False,
            }
            for order_line in orders.order_line.filtered(lambda line: not line.display_type)
        }

    @api.model
    def _prepare_sale_sync_values(self, operation):
        """Expected product lines coming from the operation sale orders."""
        orders = operation.sale_order_ids.filtered(
            lambda order: order.state in self._get_sale_sync_states()
            and order.comex_operation_id == operation
        )
        return {
            ('sale', order_line.id): {
                'product_id': order_line.product_id.id,
                'name': order_line.name,
                'product_qty': order_line.product_uom_qty,
                'product_uom': order_line.product_uom.id,
                'price_unit': order_line.price_unit,
                'qty_received': 0.0,
                'qty_delivered': order_line.qty_delivered,
                'origin_type': 'sale',
                'purchase_line_id': False,
                'sale_line_id': order_line.id,
            }
            for order_line in orders.order_line.filtered(lambda line: not line.display_type)
        }

    @api.model
    def _get_purchase_sync_states(self):
        """Purchase order states whose lines are mirrored as product lines."""
        return ('purchase', 'done')

    @api.model
    def _get_sale_sync_states(self):
        """Sale order states whose lines are mirrored as product lines."""
        return ('sale', 'done')

    def _get_sync_key(self):
        """Return the source identifier used to match a line during sync."""
        self.ensure_one()
        if self.origin_type == 'purchase':
            return ('purchase', self.purchase_line_id.id)
        if self.origin_type == 'sale':
            return ('sale', self.sale_line_id.id)
        return ('manual', self.id)

    def _write_sync_values(self, values):
        """Write only the values that actually differ, to avoid useless writes."""
        self.ensure_one()
        changes = {}
        for field_name, value in values.items():
            field = self._fields[field_name]
            current = self[field_name]
            if field.type == 'many2one':
                current = current.id
            if field.type == 'float':
                if float_compare(current or 0.0, value or 0.0, precision_digits=6):
                    changes[field_name] = value
            elif current != value:
                changes[field_name] = value
        if changes:
            self.write(changes)

    @api.model
    def _cron_sync_all_operations(self):
        """Daily safety net: resynchronise every operation with orders linked."""
        operations = self.env['comex.operation'].with_context(active_test=False).search([
            '|',
            ('purchase_order_ids', '!=', False),
            ('sale_order_ids', '!=', False),
        ])
        _logger.info("COMEX product line cron: synchronising %s operations", len(operations))
        self._sync_operations(operations)

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
