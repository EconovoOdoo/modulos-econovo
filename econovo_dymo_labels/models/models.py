# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ReportEconovoDymoLabels(models.AbstractModel):
    _name = 'report.econovo_dymo_labels.report_producttemplatelabel_dymo'
    _description = 'Econovo DYMO Labels Report'

    def _get_real_destination_location(self, product, context_data):
        """
        Obtener ubicación real de destino desde stock.move.line (ALT 4)
        Más preciso que putaway rules cuando viene de picking
        """
        if not context_data:
            return None
            
        context = context_data.get('context', {})
        
        # Método 1: Usar picking_id si existe (más directo)
        picking_id = context.get('active_id') if context.get('active_model') == 'stock.picking' else None
        
        if picking_id:
            # Buscar stock.move.line específicas del producto en este picking
            # Mantener el orden natural del picking
            move_lines = self.env['stock.move.line'].search([
                ('picking_id', '=', picking_id),
                ('product_id', '=', product.id),
                ('state', 'in', ['assigned', 'partially_available', 'confirmed', 'waiting'])
            ])
            
            if move_lines:
                # Buscar la ubicación más específica (más profunda en la jerarquía)
                locations = move_lines.mapped('location_dest_id')
                if locations:
                    # Elegir la ubicación con más niveles (más específica)
                    most_specific = max(locations, key=lambda loc: len(loc.parent_path.split('/')))
                    return most_specific.display_name
        
        # Método 2: Usar move_ids del contexto (fallback)
        move_ids = context.get('default_move_ids', [])
        if move_ids:
            # Prioridad: Buscar en move_lines primero (más específico que moves)
            move_lines = self.env['stock.move.line'].search([
                ('move_id', 'in', move_ids),
                ('product_id', '=', product.id)
            ])
            
            if move_lines:
                # Elegir la ubicación más específica
                locations = move_lines.mapped('location_dest_id')
                if locations:
                    most_specific = max(locations, key=lambda loc: len(loc.parent_path.split('/')))
                    return most_specific.display_name
            
            # Fallback a stock.move si no hay move_lines
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
        docs = self.env['product.product'].browse(docids)
        
        # Crear mapa de ubicaciones inteligente por producto (ALT 1)
        picking_location_map = {}
        for product in docs:
            # Intentar obtener ubicación real de destino (más preciso)
            real_location = self._get_real_destination_location(product, data)
            if real_location:
                picking_location_map[product.id] = real_location
        
        # Initialize report data
        report_data = {
            'doc_ids': docids,
            'doc_model': 'product.product',
            'docs': docs,
            'source_picking_info': None,
            'picking_location_map': picking_location_map,  # Nuevas ubicaciones inteligentes
        }
        
        # Add source picking information when available
        source_picking_names = []
        
        # Primero intentar desde data (viene del wizard)
        if data and 'source_picking_info' in data:
            source_picking_names = data['source_picking_info']
        
        # Si no hay información en data, intentar desde el contexto
        if not source_picking_names and data and 'context' in data:
            context = data['context']
            
            # Intentar desde move_ids en el contexto
            move_ids = context.get('default_move_ids', [])
            if move_ids:
                moves = self.env['stock.move'].browse(move_ids)
                picking_names = moves.mapped('picking_id.name')
                source_picking_names.extend([name for name in picking_names if name])
            
            # Intentar desde active_id si es un picking
            if not source_picking_names:
                active_id = context.get('active_id')
                params = context.get('params', {})
                
                # Verificar si venimos de un picking
                if params.get('model') == 'stock.picking' and params.get('id'):
                    picking_id = params.get('id')
                    picking = self.env['stock.picking'].browse(picking_id)
                    if picking.exists():
                        source_picking_names.append(picking.name)
                elif active_id:
                    # Intentar directamente con active_id
                    try:
                        picking = self.env['stock.picking'].browse(active_id)
                        if picking.exists():
                            source_picking_names.append(picking.name)
                    except:
                        pass
        
        # Filtrar nombres únicos
        if source_picking_names:
            unique_picking_names = list(set([name for name in source_picking_names if name]))
            report_data['source_picking_info'] = unique_picking_names
        
        return report_data
