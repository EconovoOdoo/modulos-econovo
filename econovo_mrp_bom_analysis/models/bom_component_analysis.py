# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class BomComponentAnalysis(models.Model):
    _name = 'bom.component.analysis'
    _description = 'BOM Component Analysis'
    _order = 'root_bom_id, level, sequence'
    _rec_name = 'display_name'

    # =========================================================================
    # IDENTIFICATION
    # =========================================================================
    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True
    )
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )

    # =========================================================================
    # BOM RELATIONSHIP
    # =========================================================================
    root_bom_id = fields.Many2one(
        comodel_name='mrp.bom',
        string='Root BOM',
        required=True,
        ondelete='cascade',
        index=True
    )
    source_bom_id = fields.Many2one(
        comodel_name='mrp.bom',
        string='Source BOM',
        help='BOM from which this line originates'
    )
    bom_line_id = fields.Many2one(
        comodel_name='mrp.bom.line',
        string='Original BOM Line',
        help='Direct link to the original BOM line'
    )

    # =========================================================================
    # HIERARCHY
    # =========================================================================
    level = fields.Integer(
        string='Level',
        default=0,
        help='Depth level in BOM structure'
    )
    parent_component_id = fields.Many2one(
        comodel_name='bom.component.analysis',
        string='Parent Component',
        ondelete='cascade'
    )
    child_component_ids = fields.One2many(
        comodel_name='bom.component.analysis',
        inverse_name='parent_component_id',
        string='Child Components'
    )
    has_children = fields.Boolean(
        string='Has Children',
        compute='_compute_has_children',
        store=True
    )

    # =========================================================================
    # PRODUCT
    # =========================================================================
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Component',
        required=True,
        index=True
    )
    product_tmpl_id = fields.Many2one(
        comodel_name='product.template',
        string='Product Template',
        related='product_id.product_tmpl_id',
        store=True
    )
    default_code = fields.Char(
        string='Internal Reference',
        related='product_id.default_code',
        store=True
    )

    # =========================================================================
    # CATEGORY (for grouping) - Mirror from product (bidirectional sync)
    # =========================================================================
    categ_id = fields.Many2one(
        comodel_name='product.category',
        string='Category',
        related='product_id.categ_id',
        readonly=False,
        store=True,
        index=True,
        help='Product category (mirror of product.categ_id).\n'
             'Changes here update the product directly.'
    )
    categ_complete_name = fields.Char(
        string='Category Full Name',
        related='categ_id.complete_name',
        store=True
    )
    origin_type = fields.Selection(
        string='Origin Type',
        related='categ_id.origin_type',
        store=True
    )

    # =========================================================================
    # QUANTITIES - Mirror from BOM line (bidirectional sync)
    # =========================================================================
    bom_line_qty = fields.Float(
        string='BOM Quantity',
        related='bom_line_id.product_qty',
        readonly=False,
        store=True,
        digits='Product Unit of Measure',
        help='Quantity in original BOM line (mirror of mrp.bom.line.product_qty).\n'
             'Changes here update the BOM line directly.\n'
             'Note: Empty if component comes from subassembly explosion.'
    )
    quantity = fields.Float(
        string='Exploded Quantity',
        digits='Product Unit of Measure',
        help='Quantity calculated in BOM explosion considering parent quantities.\n'
             'Formula: quantity = bom_line_qty × parent_quantity × ... (recursive)'
    )
    uom_id = fields.Many2one(
        comodel_name='uom.uom',
        string='UoM'
    )

    # =========================================================================
    # COSTS - Mirror from product (bidirectional sync)
    # =========================================================================
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        related='product_id.currency_id',
        store=True
    )
    standard_price = fields.Float(
        string='Unit Cost',
        related='product_id.standard_price',
        readonly=False,
        store=True,
        digits='Product Price',
        help='Product cost (mirror of product.standard_price).\n'
             'Changes here update the product directly.'
    )
    standard_price_usd = fields.Float(
        string='Unit Cost USD',
        digits='Product Price',
        help='Cost in USD. Manual field - not all products have this.'
    )
    list_price = fields.Float(
        string='Sale Price',
        related='product_id.lst_price',
        readonly=False,
        store=True,
        digits='Product Price',
        help='Product sale price (mirror of product.lst_price).\n'
             'Changes here update the product directly.'
    )
    weight = fields.Float(
        string='Weight',
        related='product_id.weight',
        readonly=False,
        store=True,
        digits='Stock Weight',
        help='Product weight (mirror of product.weight).\n'
             'Changes here update the product directly.'
    )

    # =========================================================================
    # COMPUTED TOTALS
    # =========================================================================
    total_cost = fields.Float(
        string='Total Cost',
        compute='_compute_totals',
        store=True,
        digits='Product Price',
        help='Total cost of this component in the BOM.\n'
             'Formula: total_cost = quantity × standard_price'
    )
    total_cost_usd = fields.Float(
        string='Total Cost USD',
        compute='_compute_totals',
        store=True,
        digits='Product Price',
        help='Total cost in USD currency.\n'
             'Formula: total_cost_usd = quantity × standard_price_usd'
    )
    total_weight = fields.Float(
        string='Total Weight',
        compute='_compute_totals',
        store=True,
        digits='Stock Weight',
        help='Total weight of this component in the BOM.\n'
             'Formula: total_weight = quantity × weight'
    )

    # =========================================================================
    # ANALYSIS - Cost Share Percentages
    # =========================================================================
    cost_share_global_pct = fields.Float(
        string='Global Cost %',
        compute='_compute_cost_share',
        store=True,
        digits=(5, 2),
        help='Incidencia sobre el producto final (raíz del análisis).\\n'
             'Fórmula: (costo_total_componente / costo_total_producto_final) × 100\\n'
             'Ejemplo: Si el producto final cuesta $100 y este componente $30 → 30%\\n'
             'Nota: Los componentes de nivel 1 suman 100%.'
    )
    cost_share_local_pct = fields.Float(
        string='Local Cost %',
        compute='_compute_cost_share',
        store=True,
        digits=(5, 2),
        help='Incidencia sobre el padre inmediato (subensamblaje).\\n'
             'Fórmula: (costo_total_componente / costo_total_hermanos) × 100\\n'
             'Ejemplo: Si el subensamblaje cuesta $60 y este componente $30 → 50%\\n'
             'Nota: Los hermanos (mismo padre) siempre suman 100%.'
    )
    previous_cost = fields.Float(
        string='Previous Cost',
        digits='Product Price',
        help='Unit cost from the previous analysis. Used to calculate cost variation.'
    )
    cost_variation = fields.Float(
        string='Cost Variation',
        compute='_compute_variation',
        store=True,
        help='Absolute difference between current and previous unit cost.\n'
             'Formula: cost_variation = standard_price - previous_cost\n'
             'Positive = cost increased, Negative = cost decreased.'
    )
    cost_variation_pct = fields.Float(
        string='Variation %',
        compute='_compute_variation',
        store=True,
        help='Percentage change in cost compared to previous analysis.\n'
             'Formula: cost_variation_pct = ((standard_price - previous_cost) / previous_cost) × 100\n'
             'Positive = cost increased, Negative = cost decreased.'
    )

    # =========================================================================
    # STOCK (read-only)
    # =========================================================================
    qty_available = fields.Float(
        string='On Hand',
        related='product_id.qty_available',
        digits='Product Unit of Measure'
    )
    virtual_available = fields.Float(
        string='Forecasted',
        related='product_id.virtual_available',
        digits='Product Unit of Measure'
    )
    free_qty = fields.Float(
        string='Free to Use',
        related='product_id.free_qty',
        digits='Product Unit of Measure'
    )

    # =========================================================================
    # SUPPLIER (read-only, computed)
    # =========================================================================
    supplier_name = fields.Char(
        string='Supplier',
        compute='_compute_seller_info'
    )
    supplier_price = fields.Float(
        string='Supplier Price',
        compute='_compute_seller_info',
        digits='Product Price'
    )
    supplier_delay = fields.Integer(
        string='Delivery Lead Time',
        compute='_compute_seller_info'
    )

    # =========================================================================
    # METADATA
    # =========================================================================
    is_subassembly = fields.Boolean(
        string='Is Subassembly',
        help='Indicates if this component has its own BOM'
    )
    child_bom_id = fields.Many2one(
        comodel_name='mrp.bom',
        string='Component BOM'
    )
    analysis_date = fields.Datetime(
        string='Analysis Date',
        default=fields.Datetime.now
    )

    # =========================================================================
    # COMPUTE METHODS
    # =========================================================================

    @api.depends('default_code', 'product_id.name')
    def _compute_name(self):
        for rec in self:
            if rec.default_code:
                rec.name = f"[{rec.default_code}] {rec.product_id.name}"
            else:
                rec.name = rec.product_id.name or ''

    @api.depends('name', 'level')
    def _compute_display_name(self):
        for rec in self:
            indent = "  " * rec.level
            rec.display_name = f"{indent}{rec.name}"

    @api.depends('child_component_ids')
    def _compute_has_children(self):
        for rec in self:
            rec.has_children = bool(rec.child_component_ids)

    @api.depends('quantity', 'standard_price', 'standard_price_usd', 'weight')
    def _compute_totals(self):
        for rec in self:
            rec.total_cost = rec.quantity * rec.standard_price
            rec.total_cost_usd = rec.quantity * rec.standard_price_usd
            rec.total_weight = rec.quantity * rec.weight

    @api.depends('total_cost', 'root_bom_id', 'parent_component_id', 'level')
    def _compute_cost_share(self):
        """Compute cost share percentages: global (vs total BOM) and local (vs siblings)"""
        if not self:
            return

        # Group records by root_bom_id for efficiency
        bom_ids = set(self.mapped('root_bom_id').ids)

        # Pre-fetch all data needed for calculations
        all_analysis_lines = self.search([('root_bom_id', 'in', list(bom_ids))])

        # Build lookup dictionaries
        # level_0_by_bom[bom_id] = list of level 0 lines
        # children_by_parent[parent_id] = list of child lines
        level_0_by_bom = {}
        children_by_parent = {}
        level_0_total_by_bom = {}

        for line in all_analysis_lines:
            bom_id = line.root_bom_id.id

            # Level 0 lines
            if line.level == 0:
                if bom_id not in level_0_by_bom:
                    level_0_by_bom[bom_id] = self.env['bom.component.analysis']
                level_0_by_bom[bom_id] |= line

            # Group by parent
            parent_id = line.parent_component_id.id if line.parent_component_id else f'root_{bom_id}'
            if parent_id not in children_by_parent:
                children_by_parent[parent_id] = self.env['bom.component.analysis']
            children_by_parent[parent_id] |= line

        # Calculate level 0 totals
        for bom_id, lines in level_0_by_bom.items():
            level_0_total_by_bom[bom_id] = sum(lines.mapped('total_cost'))

        # Compute percentages for each record
        for rec in self:
            bom_id = rec.root_bom_id.id

            # === GLOBAL PERCENTAGE ===
            # Based on level 0 total (avoids double counting)
            total_global = level_0_total_by_bom.get(bom_id, 0)
            if total_global > 0:
                rec.cost_share_global_pct = (rec.total_cost / total_global) * 100
            else:
                rec.cost_share_global_pct = 0

            # === LOCAL PERCENTAGE ===
            # Based on siblings (same parent)
            parent_key = rec.parent_component_id.id if rec.parent_component_id else f'root_{bom_id}'
            siblings = children_by_parent.get(parent_key, self.env['bom.component.analysis'])
            total_local = sum(siblings.mapped('total_cost'))

            if total_local > 0:
                rec.cost_share_local_pct = (rec.total_cost / total_local) * 100
            else:
                rec.cost_share_local_pct = 0

    @api.depends('standard_price', 'previous_cost')
    def _compute_variation(self):
        for rec in self:
            if rec.previous_cost and rec.previous_cost > 0:
                rec.cost_variation = rec.standard_price - rec.previous_cost
                rec.cost_variation_pct = (rec.cost_variation / rec.previous_cost) * 100
            else:
                rec.cost_variation = 0
                rec.cost_variation_pct = 0

    @api.depends('product_id')
    def _compute_seller_info(self):
        for rec in self:
            seller = rec.product_id.seller_ids[:1]
            rec.supplier_name = seller.partner_id.name if seller else ''
            rec.supplier_price = seller.price if seller else 0.0
            rec.supplier_delay = seller.delay if seller else 0

    # Note: _compute_categ_info removed - categ_complete_name and origin_type are now related fields

    # =========================================================================
    # Note: No write() override needed.
    # Fields with related= and readonly=False automatically sync bidirectionally.
    # =========================================================================

    # =========================================================================
    # ACTIONS
    # =========================================================================

    def action_open_product(self):
        """Open product form"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'product.product',
            'res_id': self.product_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_bom_line(self):
        """Open original BOM"""
        self.ensure_one()
        if self.bom_line_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'mrp.bom',
                'res_id': self.bom_line_id.bom_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

    def action_open_child_bom(self):
        """Open component's BOM"""
        self.ensure_one()
        if self.child_bom_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'mrp.bom',
                'res_id': self.child_bom_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

    def action_refresh_from_product(self):
        """Refresh data from product"""
        for rec in self:
            rec.write({
                'standard_price': rec.product_id.standard_price,
                'list_price': rec.product_id.list_price,
                'weight': rec.product_id.weight,
                'standard_price_usd': getattr(rec.product_id, 'standard_price_usd', 0.0),
            })
