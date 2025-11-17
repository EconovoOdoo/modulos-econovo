# -*- coding: utf-8 -*-

from odoo import models, fields, api


class LocationLabelLayout(models.TransientModel):
    """
    Wizard for printing location barcode labels.
    Completely standalone - no inheritance from other modules.
    """
    _name = 'location.label.layout'
    _description = 'Location Label Layout Wizard'
    
    print_format = fields.Selection([
        ('dymo_location_100x50', 'DYMO 100x50mm - Compact'),
        ('dymo_location_100x70', 'DYMO 100x70mm - Detailed'),
    ], string='Label Format', default='dymo_location_100x50', required=True,
       help='Select the label size format for printing')
    
    location_ids = fields.Many2many(
        'stock.location',
        string='Locations',
        help='Locations to print labels for'
    )
    
    location_quantity = fields.Integer(
        'Quantity per Location',
        default=1,
        required=True,
        help='Number of labels to print for each location'
    )
    
    @api.model
    def default_get(self, fields_list):
        """Get default values from context"""
        res = super().default_get(fields_list)
        
        # Get active locations from context
        active_model = self.env.context.get('active_model')
        active_ids = self.env.context.get('active_ids', [])
        
        if active_model == 'stock.location' and active_ids:
            res['location_ids'] = [(6, 0, active_ids)]
        
        return res
    
    def action_print_labels(self):
        """Print location labels based on selected format"""
        self.ensure_one()
        
        if not self.location_ids:
            return {'type': 'ir.actions.act_window_close'}
        
        # Determine which report to use
        if self.print_format == 'dymo_location_100x50':
            report_xml_id = 'econovo_location_labels.action_report_location_label_100x50'
        else:  # dymo_location_100x70
            report_xml_id = 'econovo_location_labels.action_report_location_label_100x70'
        
        # Duplicate locations if quantity > 1
        locations_to_print = self.location_ids
        if self.location_quantity > 1:
            locations_to_print = self.location_ids
            for _ in range(self.location_quantity - 1):
                locations_to_print |= self.location_ids
        
        # Get the report action
        return self.env.ref(report_xml_id).report_action(locations_to_print)
