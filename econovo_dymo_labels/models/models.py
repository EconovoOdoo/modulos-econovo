# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ReportEconovoDymoLabels(models.AbstractModel):
    _name = 'report.econovo_dymo_labels.report_producttemplatelabel_dymo'
    _description = 'Econovo DYMO Labels Report 100x70'

    def _get_real_destination_location(self, product, context_data):
        """
        Get real destination location from stock.move.line.
        More precise than putaway rules when coming from picking
        """
        if not context_data:
            return None
            
        context = context_data.get('context', {})
        
        picking_id = context.get('active_id') if context.get('active_model') == 'stock.picking' else None
        
        if picking_id:
            move_lines = self.env['stock.move.line'].search([
                ('picking_id', '=', picking_id),
                ('product_id', '=', product.id),
                ('state', 'in', ['assigned', 'partially_available', 'confirmed', 'waiting'])
            ])
            
            if move_lines:
                locations = move_lines.mapped('location_dest_id')
                if locations:
                    most_specific = max(locations, key=lambda loc: len(loc.parent_path.split('/')))
                    return most_specific.display_name
        
        move_ids = context.get('default_move_ids', [])
        if move_ids:
            move_lines = self.env['stock.move.line'].search([
                ('move_id', 'in', move_ids),
                ('product_id', '=', product.id)
            ])
            
            if move_lines:
                locations = move_lines.mapped('location_dest_id')
                if locations:
                    most_specific = max(locations, key=lambda loc: len(loc.parent_path.split('/')))
                    return most_specific.display_name
            
            moves = self.env['stock.move'].search([
                ('id', 'in', move_ids),
                ('product_id', '=', product.id)
            ], limit=1)
            
            if moves:
                return moves.location_dest_id.display_name
        
        return None

    @api.model
    def _get_report_values(self, docids, data=None):
        """
        Prepare report values for DYMO labels including source picking information when available
        """
        # Use active_ids from data if docids is empty
        if not docids and data and data.get('active_ids'):
            docids = data['active_ids']
            
        docs = self.env['product.product'].browse(docids)
        
        picking_location_map = {}
        for product in docs:
            real_location = self._get_real_destination_location(product, data)
            if real_location:
                picking_location_map[product.id] = real_location
        
        report_data = {
            'doc_ids': docids,
            'doc_model': 'product.product',
            'docs': docs,
            'source_picking_info': None,
            'picking_location_map': picking_location_map,
        }
        
        source_picking_names = []
        
        if data and 'source_picking_info' in data:
            source_picking_names = data['source_picking_info']
        
        if not source_picking_names and data and 'context' in data:
            context = data['context']
            
            move_ids = context.get('default_move_ids', [])
            if move_ids:
                moves = self.env['stock.move'].browse(move_ids)
                picking_names = moves.mapped('picking_id.name')
                source_picking_names.extend([name for name in picking_names if name])
            
            if not source_picking_names:
                active_id = context.get('active_id')
                params = context.get('params', {})
                
                if params.get('model') == 'stock.picking' and params.get('id'):
                    picking_id = params.get('id')
                    picking = self.env['stock.picking'].browse(picking_id)
                    if picking.exists():
                        source_picking_names.append(picking.name)
                elif active_id:
                    try:
                        picking = self.env['stock.picking'].browse(active_id)
                        if picking.exists():
                            source_picking_names.append(picking.name)
                    except:
                        pass
        
        if source_picking_names:
            unique_picking_names = list(set([name for name in source_picking_names if name]))
            report_data['source_picking_info'] = unique_picking_names
        
        return report_data


class ReportEconovoDymoLabels100x50(models.AbstractModel):
    _name = 'report.econovo_dymo_labels.dymo_100x50'
    _description = 'Econovo DYMO Labels Report 100x50'
    _inherit = 'report.econovo_dymo_labels.report_producttemplatelabel_dymo'

    @api.model
    def _get_report_values(self, docids, data=None):
        """
        Inherit from 100x70 report with same logic
        """
        # Use active_ids from data if docids is empty
        if not docids and data and data.get('active_ids'):
            docids = data['active_ids']
        
        return super()._get_report_values(docids, data)
