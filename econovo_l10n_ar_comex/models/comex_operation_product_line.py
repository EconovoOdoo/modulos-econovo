# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

import logging
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.tools import float_compare, float_is_zero

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
    currency_usd_id = fields.Many2one(
        'res.currency',
        string="USD Currency",
        related='operation_id.currency_usd_id',
        store=True,
    )
    price_unit = fields.Float(
        string="Unit Price",
        required=True,
        digits='Product Price',
    )
    price_subtotal = fields.Monetary(
        string="FOB Subtotal",
        compute='_compute_price_subtotal',
        store=True,
        currency_field='currency_id',
        help="Mirrors the subtotal of the purchase/sale order line this comes from, "
             "in that document's own currency.",
    )
    price_subtotal_usd = fields.Monetary(
        string="FOB Subtotal (USD)",
        compute='_compute_price_subtotal_usd',
        store=True,
        currency_field='currency_usd_id',
        help="price_subtotal converted to USD using the exchange rate of the purchase/"
             "sale order this line comes from: that document's own currency and date, "
             "not the operation's.",
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

    # Stock position
    move_ids = fields.One2many(
        'stock.move',
        'comex_product_line_id',
        string="Stock Moves",
        readonly=True,
        help="Stock moves of this line along the whole COMEX chain.",
    )
    lot_ids = fields.Many2many(
        'stock.lot',
        string="Lots/Serial Numbers",
        compute='_compute_stock_position',
        help="Lots or serial numbers received for this line.",
    )
    current_location_ids = fields.Many2many(
        'stock.location',
        string="Current Locations",
        compute='_compute_stock_position',
        search='_search_current_location_ids',
        help="Locations where the units of this line currently are.\n"
             "For tracked products it is read from the stock of their lots/serial numbers, "
             "so it stays correct after a manual relocation, a delivery or a return.\n"
             "For untracked products it is derived from the COMEX chain of stock moves and "
             "stops once the goods are nationalised and merged with the regular stock.",
    )
    current_location_display = fields.Char(
        string="Current Location",
        compute='_compute_stock_position_cache',
        store=True,
        readonly=True,
        help="Sortable text version of the current locations.\n"
             "Materialised: refreshed when the stock moves that touch these units are "
             "validated and by the daily COMEX cron.",
    )
    lot_name_display = fields.Char(
        string="Serial Numbers",
        compute='_compute_stock_position_cache',
        store=True,
        readonly=True,
        help="Sortable text version of the lots/serial numbers of this line.",
    )
    last_delivery_partner_id = fields.Many2one(
        'res.partner',
        string="Last Delivery Contact",
        compute='_compute_stock_position_cache',
        store=True,
        readonly=True,
        help="Contact of the last transfer that handed these units over, either to a "
             "customer or to a dealer.\n"
             "Empty while the goods are still in the COMEX circuit or in own stock: "
             "receipts and COMEX chain transfers carry the supplier as contact, which "
             "says nothing about who holds the goods.\n"
             "Unlike stock.lot.last_delivery_partner_id it also covers internal "
             "transfers, so a dealer is reported too.",
    )
    stock_status = fields.Selection(
        selection='_selection_stock_status',
        string="Stock Status",
        compute='_compute_stock_position',
        search='_search_stock_status',
        help="Where the units of this line stand, derived from the location usage.",
    )

    # -------------------------------------------------------------------------
    # COMPUTE METHODS
    # -------------------------------------------------------------------------
    @api.depends('product_qty', 'price_unit')
    def _compute_price_subtotal(self):
        """Calculate subtotal as quantity * unit price."""
        for line in self:
            line.price_subtotal = line.product_qty * line.price_unit

    @api.depends(
        'price_subtotal', 'company_id',
        'purchase_line_id.order_id.currency_id', 'purchase_line_id.order_id.date_order',
        'sale_line_id.order_id.currency_id', 'sale_line_id.order_id.date_order',
        'operation_id.date_operation',
    )
    def _compute_price_subtotal_usd(self):
        """Convert the subtotal to USD using the origin document's own rate."""
        usd = self.env.ref('base.USD', raise_if_not_found=False)
        for line in self:
            line.price_subtotal_usd = line._convert_price_subtotal(usd) if usd else line.price_subtotal

    def _get_origin_currency_date(self):
        """Return the (currency, date) of the document this line's amount is in.

        Manual lines have no purchase/sale order to read from: fall back to the
        operation's own currency and date as the best available reference.
        """
        self.ensure_one()
        origin_order = self.purchase_line_id.order_id or self.sale_line_id.order_id
        if origin_order:
            return origin_order.currency_id, origin_order.date_order
        return self.currency_id, self.operation_id.date_operation

    def _convert_price_subtotal(self, target_currency):
        """Convert price_subtotal from its origin document's currency and date."""
        self.ensure_one()
        origin_currency, origin_date = self._get_origin_currency_date()
        if not origin_currency or not target_currency or not self.company_id:
            return self.price_subtotal
        rate = self.env['res.currency']._get_conversion_rate(
            origin_currency, target_currency, self.company_id, origin_date,
        )
        return self.price_subtotal * rate

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
    # STOCK POSITION
    # -------------------------------------------------------------------------
    @api.model
    def _selection_stock_status(self):
        return [
            ('pending', _("Pending")),
            ('internal', _("In Own Stock")),
            ('partial', _("Partially Delivered")),
            ('delivered', _("Delivered")),
            ('returned', _("Returned")),
            ('unknown', _("Not Traceable")),
        ]

    def _compute_stock_position(self):
        """Locate the units of each line, in a single batched pass."""
        position = self._get_stock_position()
        for line in self:
            line_position = position[line.id]
            line.lot_ids = line_position['lots']
            line.current_location_ids = line_position['locations']
            line.stock_status = self._get_stock_status(
                line_position['locations'],
                line_position['has_moves'],
                line_position['returned'],
            )

    def _compute_stock_position_cache(self):
        """Materialise the sortable version of the stock position.

        These columns have no `depends`: stock does not change through the line
        itself, so they are refreshed explicitly by `_refresh_stock_position_cache`.
        """
        position = self._get_stock_position()
        partners = self._get_last_delivery_partners(position)
        for line in self:
            line_position = position[line.id]
            line.current_location_display = ', '.join(
                sorted(line_position['locations'].mapped('complete_name'))
            )
            line.lot_name_display = ', '.join(sorted(line_position['lots'].mapped('name')))
            line.last_delivery_partner_id = partners.get(line.id, False)

    def _refresh_stock_position_cache(self):
        """Queue the materialised stock position columns for recomputation."""
        for field_name in ('current_location_display', 'lot_name_display',
                           'last_delivery_partner_id'):
            self.env.add_to_compute(self._fields[field_name], self)

    def _get_last_delivery_partners(self, position):
        """Return {line_id: partner} of the last transfer that handed the units over.

        Inbound logistics is excluded: a receipt and the COMEX chain transfers
        carry the supplier as contact, which says nothing about who holds the
        goods now.
        """
        partners = {}
        moves_by_line = self._get_done_moves_by_line()
        for line in self:
            lots = position[line.id]['lots']
            if lots:
                move_line = self.env['stock.move.line'].sudo().search([
                    ('lot_id', 'in', lots.ids),
                    ('state', '=', 'done'),
                    ('move_id.picking_id.partner_id', '!=', False),
                    ('move_id.picking_id.picking_type_id.code', '!=', 'incoming'),
                    ('move_id.picking_id.picking_type_id.is_comex_import', '=', False),
                ], order='date desc', limit=1)
                if move_line:
                    partners[line.id] = move_line.move_id.picking_id.partner_id.id
                    continue
            candidates = moves_by_line[line.id].filtered(
                lambda move: move.picking_id.partner_id
                and move.picking_id.picking_type_id.code != 'incoming'
                and not move.picking_id.picking_type_id.is_comex_import
            ).sorted('date', reverse=True)
            if candidates:
                partners[line.id] = candidates[0].picking_id.partner_id.id
        return partners

    def _get_stock_position(self):
        """Return {line_id: {'lots', 'locations', 'has_moves', 'returned'}}."""
        lots = self.env['stock.lot']
        locations = self.env['stock.location']
        position = {
            line.id: {
                'lots': lots,
                'locations': locations,
                'has_moves': False,
                'returned': False,
            }
            for line in self
        }
        if not self:
            return position

        moves_by_line = self._get_done_moves_by_line()
        for line_id, moves in moves_by_line.items():
            position[line_id]['has_moves'] = bool(moves)

        self._fill_tracked_position(position, moves_by_line)
        self._fill_untracked_position(position, moves_by_line)
        return position

    def _get_done_moves_by_line(self):
        """Return the done stock moves of each line, keyed by line id.

        Lines whose historical moves were never linked fall back to matching by
        operation and product, which is the best attribution available for them.
        """
        moves_by_line = {line.id: self.env['stock.move'] for line in self}
        linked_moves = self.env['stock.move'].sudo().search([
            ('comex_product_line_id', 'in', self.ids),
            ('state', '=', 'done'),
        ])
        for move in linked_moves:
            moves_by_line[move.comex_product_line_id.id] |= move

        unlinked_lines = self.filtered(lambda line: not moves_by_line[line.id])
        if not unlinked_lines:
            return moves_by_line

        fallback_moves = self.env['stock.move'].sudo().search([
            ('comex_operation_id', 'in', unlinked_lines.operation_id.ids),
            ('product_id', 'in', unlinked_lines.product_id.ids),
            ('comex_product_line_id', '=', False),
            ('state', '=', 'done'),
        ])
        moves_by_key = defaultdict(lambda: self.env['stock.move'])
        for move in fallback_moves:
            moves_by_key[(move.comex_operation_id.id, move.product_id.id)] |= move
        for line in unlinked_lines:
            moves_by_line[line.id] = moves_by_key[(line.operation_id.id, line.product_id.id)]
        return moves_by_line

    def _fill_tracked_position(self, position, moves_by_line):
        """Locate tracked lines from the stock of their lots/serial numbers."""
        tracked_lines = self.filtered(
            lambda line: line.product_id.tracking in ('serial', 'lot')
        )
        if not tracked_lines:
            return

        line_by_move = {}
        for line in tracked_lines:
            for move in moves_by_line[line.id]:
                line_by_move[move.id] = line.id

        move_lines = self.env['stock.move.line'].sudo().search([
            ('move_id', 'in', list(line_by_move)),
            ('lot_id', '!=', False),
            ('state', '=', 'done'),
        ])
        if not move_lines:
            return

        lines_by_lot = defaultdict(set)
        for move_line in move_lines:
            line_id = line_by_move[move_line.move_id.id]
            position[line_id]['lots'] |= move_line.lot_id
            lines_by_lot[move_line.lot_id.id].add(line_id)

        all_lots = self.env['stock.lot'].browse(list(lines_by_lot))
        # Quants are the only reliable source: they follow manual relocations,
        # deliveries and returns, and unlike stock.lot.location_id they also
        # describe a lot split across several locations.
        quants = self.env['stock.quant'].sudo().search([
            ('lot_id', 'in', all_lots.ids),
            ('quantity', '>', 0),
        ])
        for quant in quants:
            for line_id in lines_by_lot[quant.lot_id.id]:
                position[line_id]['locations'] |= quant.location_id

        returned_move_lines = self.env['stock.move.line'].sudo().search([
            ('lot_id', 'in', all_lots.ids),
            ('move_id.origin_returned_move_id', '!=', False),
            ('state', '=', 'done'),
        ])
        for move_line in returned_move_lines:
            for line_id in lines_by_lot[move_line.lot_id.id]:
                position[line_id]['returned'] = True

    def _fill_untracked_position(self, position, moves_by_line):
        """Locate untracked lines from the net balance of their COMEX moves."""
        untracked_lines = self.filtered(
            lambda line: line.product_id.tracking not in ('serial', 'lot')
        )
        if not untracked_lines:
            return

        balances = defaultdict(lambda: defaultdict(float))
        for line in untracked_lines:
            for move in moves_by_line[line.id]:
                balances[line.id][move.location_dest_id.id] += move.quantity
                balances[line.id][move.location_id.id] -= move.quantity

        candidate_ids = {
            location_id
            for line_balances in balances.values()
            for location_id, quantity in line_balances.items()
            if float_compare(quantity, 0.0, precision_digits=6) > 0
        }
        if not candidate_ids:
            return

        available = self._get_available_quantities(untracked_lines, candidate_ids)
        for line in untracked_lines:
            for location_id, quantity in balances[line.id].items():
                if float_compare(quantity, 0.0, precision_digits=6) <= 0:
                    continue
                # Drop locations that no longer hold stock: the goods were moved
                # away by an inventory adjustment or a non-COMEX transfer.
                key = (line.company_id.id, line.product_id.id, location_id)
                if float_is_zero(available.get(key, 0.0), precision_digits=6):
                    continue
                position[line.id]['locations'] |= self.env['stock.location'].browse(location_id)

    @api.model
    def _get_available_quantities(self, lines, location_ids):
        """Return {(company, product, location): quantity} for the given scope."""
        groups = self.env['stock.quant'].sudo().read_group(
            [
                ('company_id', 'in', lines.company_id.ids),
                ('product_id', 'in', lines.product_id.ids),
                ('location_id', 'in', list(location_ids)),
            ],
            ['quantity:sum'],
            ['company_id', 'product_id', 'location_id'],
            lazy=False,
        )
        return {
            (group['company_id'][0], group['product_id'][0], group['location_id'][0]):
                group['quantity']
            for group in groups
            if group['company_id'] and group['product_id'] and group['location_id']
        }

    @api.model
    def _get_stock_status(self, locations, has_moves, returned):
        """Classify a position using the location usage, without naming stages."""
        if returned:
            return 'returned'
        if not locations:
            return 'unknown' if has_moves else 'pending'

        usages = set(locations.mapped('usage'))
        own = usages & {'internal', 'transit'}
        delivered = 'customer' in usages
        if own and delivered:
            return 'partial'
        if delivered:
            return 'delivered'
        if own == usages:
            return 'internal'
        return 'unknown'

    def _search_current_location_ids(self, operator, value):
        """Filter lines by where their units currently are."""
        lines = self.search([])
        positions = lines._get_stock_position()
        target_ids = set(self.env['stock.location']._search([('id', operator, value)]))
        matching_ids = [
            line_id
            for line_id, position in positions.items()
            if target_ids & set(position['locations'].ids)
        ]
        return [('id', 'in', matching_ids)]

    def _search_stock_status(self, operator, value):
        """Filter lines by stock status."""
        if operator not in ('=', '!=', 'in', 'not in'):
            raise NotImplementedError(
                _("Unsupported operator %s on the stock status.", operator)
            )
        values = value if isinstance(value, (list, tuple)) else [value]
        lines = self.search([])
        positions = lines._get_stock_position()
        matching_ids = [
            line.id
            for line in lines
            if self._get_stock_status(
                positions[line.id]['locations'],
                positions[line.id]['has_moves'],
                positions[line.id]['returned'],
            ) in values
        ]
        if operator in ('!=', 'not in'):
            return [('id', 'not in', matching_ids)]
        return [('id', 'in', matching_ids)]

    def _assign_stock_moves(self):
        """Link the stock moves of each line, including the already existing chain.

        Moves that already belong to another line are never reassigned, so
        historical merged moves cannot be stolen from their line.
        """
        for line in self:
            origin_moves = line.purchase_line_id.move_ids | line.sale_line_id.move_ids
            if not origin_moves:
                continue
            chain = origin_moves
            frontier = origin_moves
            while frontier:
                frontier = frontier.move_dest_ids - chain
                chain |= frontier
            to_assign = chain.filtered(
                lambda move: not move.comex_product_line_id
                and move.product_id == line.product_id
            )
            if to_assign:
                to_assign.sudo().write({'comex_product_line_id': line.id})
        self._refresh_stock_position_cache()

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

        self.search([('operation_id', '=', operation.id)])._assign_stock_moves()

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
        self.search([('operation_id', 'in', operations.ids)])._refresh_stock_position_cache()

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
