# -*- coding: utf-8 -*-

from odoo import models


class StockLocation(models.Model):
    _inherit = 'stock.location'

    def action_print_location_label(self):
        """
        Open wizard to select label format and print location labels.
        
        Returns:
            ir.actions.act_window: Action to open the label layout wizard
        """
        return self.env['ir.actions.act_window']._for_xml_id(
            'econovo_location_labels.action_open_location_label_layout'
        )
