# -*- coding: utf-8 -*-

from odoo import models, fields, api

class ReportEconovoDymoLabels(models.AbstractModel):
    _name = 'report.econovo_dymo_labels.report_producttemplatelabel_dymo'
    _description = 'Econovo DYMO Labels Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """
        Prepare report values for DYMO labels including source picking information when available
        """
        docs = self.env['product.product'].browse(docids)
        
        # Initialize report data
        report_data = {
            'doc_ids': docids,
            'doc_model': 'product.product',
            'docs': docs,
            'source_picking_info': None,
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
