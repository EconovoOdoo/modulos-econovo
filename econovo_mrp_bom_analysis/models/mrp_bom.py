# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    component_analysis_count = fields.Integer(
        string='Analysis Lines',
        compute='_compute_component_analysis_count'
    )
    last_analysis_date = fields.Datetime(
        string='Last Analysis Date',
        readonly=True
    )

    def _compute_component_analysis_count(self):
        Analysis = self.env['bom.component.analysis']
        for bom in self:
            bom.component_analysis_count = Analysis.search_count([
                ('root_bom_id', '=', bom.id)
            ])

    def action_open_component_analysis(self):
        """Open or generate component analysis"""
        self.ensure_one()

        Analysis = self.env['bom.component.analysis']
        existing = Analysis.search([('root_bom_id', '=', self.id)], limit=1)

        if not existing:
            self._generate_component_analysis()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Component Analysis: %s') % self.display_name,
            'res_model': 'bom.component.analysis',
            'view_mode': 'tree,pivot,graph',
            'domain': [('root_bom_id', '=', self.id)],
            'context': {
                'default_root_bom_id': self.id,
                'search_default_group_by_category': 1,
            },
            'target': 'current',
        }

    def action_regenerate_analysis(self):
        """Regenerate component analysis"""
        self.ensure_one()

        self.env['bom.component.analysis'].search([
            ('root_bom_id', '=', self.id)
        ]).unlink()

        self._generate_component_analysis()

        return self.action_open_component_analysis()

    def _generate_component_analysis(self):
        """Generate analysis using native Odoo BOM structure report"""
        self.ensure_one()

        report = self.env['report.mrp.report_bom_structure']
        warehouse = self.env['stock.warehouse'].search([
            ('company_id', '=', self.env.company.id)
        ], limit=1)

        product = self.product_id or self.product_tmpl_id.product_variant_id

        bom_data = report._get_bom_data(
            self,
            warehouse,
            product=product,
            line_qty=self.product_qty,
            level=0
        )

        self._create_analysis_lines(bom_data, parent=None, level=0, sequence=0)
        # cost_share_pct is now computed automatically when total_cost changes

        self.last_analysis_date = fields.Datetime.now()

        return True

    def _create_analysis_lines(self, bom_data, parent, level, sequence):
        """Create analysis lines recursively"""
        Analysis = self.env['bom.component.analysis']
        seq = sequence

        for comp in bom_data.get('components', []):
            product = comp['product']
            seq += 10

            # Find the bom_line_id - the native report doesn't include it directly
            # We need to find it from the parent BOM and product
            bom_line = self.env['mrp.bom.line']
            source_bom_id = bom_data.get('bom_id') or self.id
            if source_bom_id:
                source_bom = self.env['mrp.bom'].browse(source_bom_id)
                # Search for the line matching this product in the source BOM
                matching_lines = source_bom.bom_line_ids.filtered(
                    lambda l, p=product: l.product_id.id == p.id
                )
                if matching_lines:
                    bom_line = matching_lines[0]

            # Calculate quantity from BOM line
            bom_line_qty = comp.get('base_bom_line_qty', 0) or comp['quantity']

            # Note: Fields with related= are automatically populated from product_id and bom_line_id
            # We only need to set: product_id, bom_line_id, quantity, and non-related fields
            vals = {
                'root_bom_id': self.id,
                'source_bom_id': bom_data.get('bom_id') or self.id,
                'bom_line_id': bom_line.id if bom_line else False,
                'parent_component_id': parent.id if parent else False,
                'level': level,
                'sequence': seq,
                'product_id': product.id,
                # Related fields (auto-populated): categ_id, standard_price, list_price, weight, bom_line_qty
                'quantity': comp['quantity'],
                'uom_id': comp['uom'].id,
                # Non-related fields that need explicit values:
                'standard_price_usd': getattr(product, 'standard_price_usd', 0.0),
                'previous_cost': product.standard_price,
                'is_subassembly': bool(comp.get('bom_id')),
                'child_bom_id': comp.get('bom_id'),
            }

            new_line = Analysis.create(vals)

            if comp.get('components'):
                seq = self._create_analysis_lines(
                    comp,
                    parent=new_line,
                    level=level + 1,
                    sequence=seq
                )

        return seq

    # Method _compute_cost_shares removed - cost_share_pct is now a computed field
