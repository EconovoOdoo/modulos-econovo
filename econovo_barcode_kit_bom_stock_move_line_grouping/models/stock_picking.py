# -*- coding: utf-8 -*-

from odoo import models


class StockPicking(models.Model):
    """Extends stock.picking to expose kit/BOM fields to the barcode frontend."""
    _inherit = 'stock.picking'

    def _get_stock_barcode_data(self):
        """
        Override to include description_bom_line field in stock.move records.
        
        Returns:
            dict: Barcode data with enhanced stock.move records including BOM information
        """
        data = super()._get_stock_barcode_data()
        moves = self.move_ids
        
        if moves:
            move_data = []
            for move in moves:
                move_data.append({
                    'id': move.id,
                    'description_bom_line': move.description_bom_line,
                    'bom_line_id': move.bom_line_id.id if move.bom_line_id else False,
                })
            
            if 'stock.move' not in data['records']:
                data['records']['stock.move'] = []
            
            data['records']['stock.move'].extend(move_data)
        
        return data
