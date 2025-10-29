# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models

import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        """Override to propagate the current user through context.
        
        This ensures that when MOs are created from sales orders,
        the user-level draft policies are checked against the user
        who clicked "Confirm" rather than the system user (OdooBot).
        """
        # Capture the current user ID before Odoo switches context
        current_user_id = self.env.uid
        
        _logger.debug(
            "Sale Order confirmation initiated by user ID: %s (%s)",
            current_user_id,
            self.env.user.name
        )
        
        # Propagate the original user through context
        return super(SaleOrder, self.with_context(
            original_user_id=current_user_id
        )).action_confirm()
