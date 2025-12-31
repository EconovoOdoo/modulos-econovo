# -*- coding: utf-8 -*-
"""
Stock Quant Relocator - Simple method wrapper
Add this class to any Odoo module or directly extend stock.quant
"""

from odoo import api, models


class StockQuantRelocator(models.Model):
    _inherit = 'stock.quant'

    @api.model
    def quant_move_via_rpc(self, quant_id, message, location_dest_id):
        """
        Wrapper for move_quants that properly handles parameters from XML-RPC.
        
        Args:
            quant_id: ID of stock.quant (integer)
            message: Reason message (string)
            location_dest_id: Destination location ID (integer)
            
        Returns:
            True if successful (boolean, XML-RPC serializable)
        """
        try:
            # Get the quant
            quant = self.browse(quant_id)
            if not quant:
                raise ValueError(f'Quant {quant_id} not found')
            
            # Get destination location as object
            location_dest = self.env['stock.location'].browse(location_dest_id)
            if not location_dest:
                raise ValueError(f'Location {location_dest_id} not found')
            
            # Call move_quants with proper objects
            # This method expects recordsets with full object context
            quant.move_quants(message, location_dest)
            
            return True
            
        except Exception as e:
            # Return error message for logging
            raise ValueError(f'Failed to relocate quant {quant_id}: {str(e)}')


