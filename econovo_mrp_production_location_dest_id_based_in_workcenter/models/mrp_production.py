# -*- coding: utf-8 -*-

from odoo import fields, models, api


class MrpProduction(models.Model):
    _inherit = 'mrp.production'    # Add computed field to show which workcenter destination is being used
    workcenter_location_dest_id = fields.Many2one(
        'stock.location',
        string='Workcenter Destination',
        compute='_compute_workcenter_location_dest',
        store=True,
        help="Destination location determined by the workcenter configuration"
    )

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
        """Override the original method to consider workcenter destination locations"""
        for production in self:
            # First, apply the standard logic to get fallback location if needed
            if not production.picking_type_id.default_location_src_id or not production.picking_type_id.default_location_dest_id:
                company_id = production.company_id.id if (production.company_id and production.company_id in self.env.companies) else self.env.company.id
                fallback_loc = self.env['stock.warehouse'].search([('company_id', '=', company_id)], limit=1).lot_stock_id
            else:
                fallback_loc = None
            
            # Set source location (unchanged from standard behavior)
            if production.picking_type_id.default_location_src_id:
                production.location_src_id = production.picking_type_id.default_location_src_id
            elif fallback_loc:
                production.location_src_id = fallback_loc
            
            # For destination location, check if any workcenter has a custom destination
            # Use the LAST workcenter with destination configured (makes manufacturing sense)
            workcenter_dest = None
            for workorder in production.workorder_ids:
                if workorder.workcenter_id.location_dest_id:
                    workcenter_dest = workorder.workcenter_id.location_dest_id
                    # Don't break - continue to find the last workcenter with destination
            
            # Set destination location: workcenter destination > default from picking type > fallback
            if workcenter_dest:
                production.location_dest_id = workcenter_dest
            elif production.picking_type_id.default_location_dest_id:
                production.location_dest_id = production.picking_type_id.default_location_dest_id
            elif fallback_loc:
                production.location_dest_id = fallback_loc

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
