# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class BomCostReport(models.AbstractModel):
    """BOM Cost Analysis Report.
    
    This model extends report.mrp.report_bom_structure to provide cost analysis
    data in a format compatible with account_reports OWL component.
    
    Key features:
    - Reuses optimized _get_bom_data() from mrp.report_bom_structure
    - Transforms data into account_reports-compatible line format
    - Provides methods for fold/unfold operations
    - Calculates cost incidence percentages per category/component
    """
    _name = 'report.econovo.bom_cost_analysis'
    _description = 'BOM Cost Analysis Report'
    _inherit = 'report.mrp.report_bom_structure'

    # =========================================================================
    # MAIN ENTRY POINTS
    # =========================================================================
    
    @api.model
    def get_report_data(self, bom_id, options=None):
        """Main method to get report data for OWL component.
        
        Args:
            bom_id: ID of the mrp.bom to analyze
            options: Dict with options like:
                - quantity: BOM quantity to analyze
                - variant_id: Product variant ID
                - warehouse_id: Warehouse ID for stock availability
                - unfolded_lines: List of unfolded line IDs
                - unfold_all: Boolean to unfold all lines
        
        Returns:
            Dict with report data compatible with account_reports format
        """
        options = options or {}
        bom = self.env['mrp.bom'].browse(bom_id)
        if not bom.exists():
            return {'lines': [], 'columns': []}
        
        # Get quantity and variant from options
        quantity = options.get('quantity', bom.product_qty or 1.0)
        variant_id = options.get('variant_id')
        
        # Set warehouse context if provided
        if options.get('warehouse_id'):
            self = self.with_context(warehouse=options['warehouse_id'])
        
        # Get BOM data using parent's optimized method
        bom_data = self._get_report_data(bom_id, searchQty=quantity, searchVariant=variant_id)
        
        # The 'lines' key contains the top-level BOM dict with nested 'components'
        top_level_bom = bom_data.get('lines', {})
        
        # Transform to account_reports-compatible format
        lines = self._transform_bom_data_to_lines(
            top_level_bom, 
            options,
            total_bom_cost=top_level_bom.get('bom_cost', 0) or 1
        )
        
        # Calculate totals
        total_cost = top_level_bom.get('bom_cost', 0)
        currency = top_level_bom.get('currency') or self.env.company.currency_id
        
        return {
            'lines': lines,
            'columns': self._get_columns(),
            'bom_id': bom_id,
            'bom_name': bom.display_name,
            'bom_product': bom.product_id.display_name or bom.product_tmpl_id.display_name,
            'bom_quantity': quantity,
            'total_cost': total_cost,
            'currency_id': currency.id,
            'currency_symbol': currency.symbol,
            'unfolded_lines': options.get('unfolded_lines', []),
        }
    
    @api.model
    def get_expanded_lines(self, bom_id, line_id, options=None):
        """Get children lines when expanding a node.
        
        Args:
            bom_id: Root BOM ID
            line_id: ID of the line being expanded
            options: Report options
        
        Returns:
            List of child line dicts
        """
        options = options or {}
        
        # Get full BOM data
        report_data = self.get_report_data(bom_id, options)
        
        # Find the line and return its children
        all_lines = report_data.get('lines', [])
        
        children = []
        found_parent = False
        parent_level = 0
        
        for line in all_lines:
            if line['id'] == line_id:
                found_parent = True
                parent_level = line['level']
                continue
            
            if found_parent:
                if line['level'] == parent_level + 1 and line.get('parent_id') == line_id:
                    children.append(line)
                elif line['level'] <= parent_level:
                    # We've passed all children
                    break
        
        return children
    
    # =========================================================================
    # DATA TRANSFORMATION
    # =========================================================================
    
    @api.model
    def _transform_bom_data_to_lines(self, bom_data, options, parent_id=None, index='', total_bom_cost=1):
        """Transform mrp.report_bom_structure data to account_reports format.
        
        Recursively transforms the nested component structure into a flat
        list of lines with proper hierarchy information.
        """
        lines = []
        unfolded_lines = options.get('unfolded_lines', [])
        unfold_all = options.get('unfold_all', True)  # Default to unfold all
        
        if not bom_data:
            return lines
        
        # Create line for this BOM/component
        line_id = self._get_line_id(bom_data, index)
        has_children = bool(bom_data.get('components'))
        is_unfolded = line_id in unfolded_lines or unfold_all
        
        line = {
            'id': line_id,
            'name': bom_data.get('name', ''),
            'level': bom_data.get('level', 0),
            'parent_id': parent_id,
            'unfoldable': has_children,
            'unfolded': is_unfolded and has_children,
            'columns': self._get_line_columns(bom_data, total_bom_cost),
            'type': bom_data.get('type', 'component'),
            'product_id': bom_data.get('product_id'),
            'bom_id': bom_data.get('bom_id'),
            'visible': True,
            'class': self._get_line_class(bom_data),
        }
        
        lines.append(line)
        
        # Process children if unfolded
        if has_children and (is_unfolded or unfold_all):
            for comp_idx, component in enumerate(bom_data.get('components', [])):
                child_index = f"{index}{comp_idx}"
                child_lines = self._transform_bom_data_to_lines(
                    component,
                    options,
                    parent_id=line_id,
                    index=child_index,
                    total_bom_cost=total_bom_cost
                )
                lines.extend(child_lines)
        
        return lines
    
    @api.model
    def _get_line_id(self, data, index):
        """Generate unique line ID."""
        if data.get('bom_id'):
            return f"bom_{data['bom_id']}_{index}"
        elif data.get('product_id'):
            return f"component_{data['product_id']}_{index}"
        return f"line_{index}"
    
    @api.model
    def _get_line_columns(self, data, total_bom_cost):
        """Get column values for a line."""
        bom_cost = data.get('bom_cost', 0)
        prod_cost = data.get('prod_cost', 0)
        quantity = data.get('quantity', 0)
        
        # Calculate cost incidence percentage
        cost_pct = (bom_cost / total_bom_cost * 100) if total_bom_cost else 0
        
        # Get category name
        product = data.get('product')
        categ_name = ''
        if product:
            categ_name = product.categ_id.name if product.categ_id else ''
        
        return [
            {
                'name': categ_name,
                'no_format': categ_name,
                'class': 'text-start',
            },
            {
                'name': self._format_float(quantity, digits=2),
                'no_format': quantity,
                'class': 'text-end',
            },
            {
                'name': data.get('uom_name', ''),
                'no_format': data.get('uom_name', ''),
                'class': 'text-start',
            },
            {
                'name': self._format_monetary(prod_cost),
                'no_format': prod_cost,
                'class': 'text-end',
            },
            {
                'name': self._format_monetary(bom_cost),
                'no_format': bom_cost,
                'class': 'text-end',
            },
            {
                'name': f"{cost_pct:.1f}%",
                'no_format': cost_pct,
                'class': 'text-end fw-bold' if cost_pct >= 10 else 'text-end',
            },
        ]
    
    @api.model
    def _get_line_class(self, data):
        """Get CSS class for line based on type and level."""
        classes = []
        
        if data.get('type') == 'bom':
            classes.append('o_bom_line')
        else:
            classes.append('o_component_line')
        
        level = data.get('level', 0)
        if level == 0:
            classes.append('fw-bold')
        
        return ' '.join(classes)
    
    @api.model
    def _get_columns(self):
        """Get column definitions for the report."""
        return [
            {'name': _('Category'), 'class': 'text-start'},
            {'name': _('Quantity'), 'class': 'text-end'},
            {'name': _('UoM'), 'class': 'text-start'},
            {'name': _('Unit Cost'), 'class': 'text-end'},
            {'name': _('Total Cost'), 'class': 'text-end'},
            {'name': _('% Cost'), 'class': 'text-end'},
        ]
    
    # =========================================================================
    # FORMATTING HELPERS
    # =========================================================================
    
    @api.model
    def _format_float(self, value, digits=2):
        """Format float value."""
        if value is None or value is False:
            return ''
        return f"{value:,.{digits}f}"
    
    @api.model
    def _format_monetary(self, value):
        """Format monetary value with currency symbol."""
        if value is None or value is False:
            return ''
        currency = self.env.company.currency_id
        return f"{currency.symbol} {value:,.2f}"
    
    # =========================================================================
    # CATEGORY SUMMARY
    # =========================================================================
    
    @api.model
    def get_category_summary(self, bom_id, options=None):
        """Get cost summary grouped by category.
        
        Returns list of categories with their total cost and percentage.
        Useful for pie chart visualization.
        """
        options = options or {}
        report_data = self.get_report_data(bom_id, {**options, 'unfold_all': True})
        
        category_totals = {}
        total_cost = 0
        
        for line in report_data.get('lines', []):
            product_id = line.get('product_id')
            if not product_id:
                continue
            
            product = self.env['product.product'].browse(product_id)
            categ = product.categ_id
            categ_name = categ.name if categ else _('Uncategorized')
            
            cost = line['columns'][4]['no_format']  # Total Cost column
            
            if categ_name not in category_totals:
                category_totals[categ_name] = {
                    'name': categ_name,
                    'cost': 0,
                    'categ_id': categ.id if categ else False,
                    'color': getattr(categ, 'color', 0) if categ else 0,
                }
            category_totals[categ_name]['cost'] += cost
            total_cost += cost
        
        # Calculate percentages
        result = []
        for categ_data in category_totals.values():
            categ_data['percentage'] = (categ_data['cost'] / total_cost * 100) if total_cost else 0
            result.append(categ_data)
        
        # Sort by cost descending
        result.sort(key=lambda x: x['cost'], reverse=True)
        
        return {
            'categories': result,
            'total_cost': total_cost,
        }
