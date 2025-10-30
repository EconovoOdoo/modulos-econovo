# -*- coding: utf-8 -*-

from odoo import fields, models, api


class MrpProduction(models.Model):
    _inherit = 'mrp.production'
    
    # Add computed field to show which workcenter destination is being used
    workcenter_location_dest_id = fields.Many2one(
        'stock.location',
        string='Workcenter Destination',
        compute='_compute_workcenter_location_dest',
        store=True,
        help="Destination location determined by the workcenter configuration"
    )

    @api.model
    def default_get(self, fields_list):
        """Override default_get to ensure location_src_id and location_dest_id have values
        
        This fixes NotNullViolation error during merge operations when computed fields
        are not triggered before database INSERT (v17.0.1.1.0).
        """
        res = super(MrpProduction, self).default_get(fields_list)
        
        # If location_src_id or location_dest_id are requested but not set, compute defaults
        if ('location_src_id' in fields_list and not res.get('location_src_id')) or \
           ('location_dest_id' in fields_list and not res.get('location_dest_id')):
            
            # Get picking_type from context or use default
            picking_type_id = res.get('picking_type_id') or self.env.context.get('default_picking_type_id')
            
            if picking_type_id:
                picking_type = self.env['stock.picking.type'].browse(picking_type_id)
                
                # Compute fallback location from warehouse
                company_id = self.env.company.id
                fallback_loc = self.env['stock.warehouse'].search([('company_id', '=', company_id)], limit=1).lot_stock_id
                
                # Set location_src_id if requested and not set
                if 'location_src_id' in fields_list and not res.get('location_src_id'):
                    if picking_type.default_location_src_id:
                        res['location_src_id'] = picking_type.default_location_src_id.id
                    elif fallback_loc:
                        res['location_src_id'] = fallback_loc.id
                
                # Set location_dest_id if requested and not set
                if 'location_dest_id' in fields_list and not res.get('location_dest_id'):
                    if picking_type.default_location_dest_id:
                        res['location_dest_id'] = picking_type.default_location_dest_id.id
                    elif fallback_loc:
                        res['location_dest_id'] = fallback_loc.id
        
        return res


    @api.depends('workorder_ids.workcenter_id.location_dest_id')
    def _compute_workcenter_location_dest(self):
        """Compute the destination location based on workcenter configuration"""
        for production in self:
            workcenter_dest = False
            
            # Find the LAST workcenter with a configured destination location
            # This makes manufacturing sense as the last operation determines final location
            if production.workorder_ids:
                for workorder in production.workorder_ids:
                    if workorder.workcenter_id and workorder.workcenter_id.location_dest_id:
                        workcenter_dest = workorder.workcenter_id.location_dest_id
                        # Don't break - continue to find the last workcenter with destination
            
            production.workcenter_location_dest_id = workcenter_dest

    @api.depends('picking_type_id', 'workorder_ids', 'workorder_ids.workcenter_id.location_dest_id')
    def _compute_locations(self):
        """Override the original method to consider workcenter destination locations
        
        IMPORTANT: Always computes fallback location to handle merge scenarios where
        workorders are not yet created during MO creation (fixed in v17.0.1.1.0).
        """
        for production in self:
            # ALWAYS compute fallback location (needed for merge and edge cases)
            # This ensures location_src_id and location_dest_id are never NULL
            company_id = production.company_id.id if (production.company_id and production.company_id in self.env.companies) else self.env.company.id
            fallback_loc = self.env['stock.warehouse'].search([('company_id', '=', company_id)], limit=1).lot_stock_id
            
            # Set source location with proper fallback chain
            if production.picking_type_id.default_location_src_id:
                production.location_src_id = production.picking_type_id.default_location_src_id
            elif fallback_loc:
                production.location_src_id = fallback_loc
            else:
                # Ultimate fallback - defensive programming for edge cases
                production.location_src_id = False
            
            # For destination location, check if any workcenter has a custom destination
            # Use the LAST workcenter with destination configured (makes manufacturing sense)
            workcenter_dest = None
            for workorder in production.workorder_ids:
                if workorder.workcenter_id.location_dest_id:
                    workcenter_dest = workorder.workcenter_id.location_dest_id
                    # Don't break - continue to find the last workcenter with destination
            
            # Set destination location with proper priority and fallback chain
            # Priority: workcenter destination > picking type default > warehouse fallback
            if workcenter_dest:
                production.location_dest_id = workcenter_dest
            elif production.picking_type_id.default_location_dest_id:
                production.location_dest_id = production.picking_type_id.default_location_dest_id
            elif fallback_loc:
                production.location_dest_id = fallback_loc
            else:
                # Ultimate fallback - defensive programming for edge cases
                production.location_dest_id = False

    def _get_workcenter_destination_info(self):
        """Helper method to get information about workcenter destinations for this production"""
        workcenters_with_dest = []
        for workorder in self.workorder_ids:
            if workorder.workcenter_id.location_dest_id:
                workcenters_with_dest.append({
                    'workcenter': workorder.workcenter_id,
                    'operation': workorder.operation_id,
                    'destination': workorder.workcenter_id.location_dest_id,
                })
        return workcenters_with_dest

    def action_view_workcenter_destinations(self):
        """Action to show workcenter destination information"""
        self.ensure_one()
        
        info = self._get_workcenter_destination_info()
        if not info:
            return {'type': 'ir.actions.act_window_close'}
        
        # Create a message to show the workcenter destination information
        message = "Workcenter Destination Configuration: "
        for item in info:
            message += item['workcenter'].name + " -> " + item['destination'].complete_name + "; "
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Workcenter Destinations',
                'message': message,
                'type': 'info',
                'sticky': True,
            }
        }
