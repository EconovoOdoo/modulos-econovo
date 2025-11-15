# -*- coding: utf-8 -*-
###############################################################################
#
#    Jose D. Leonett
#
#    Copyright (C) 2024-TODAY Jose D. Leonett
#    Author: Jose D. Leonett (odoo@econovo.com)
#
#    You can modify it under the terms of the GNU AFFERO
#    GENERAL PUBLIC LICENSE (AGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU AFFERO GENERAL PUBLIC LICENSE (AGPL v3) for more details.
#
#    You should have received a copy of the GNU AFFERO GENERAL PUBLIC LICENSE
#    (AGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
###############################################################################
from odoo import fields, models


class StockLocation(models.Model):
    """Extends stock.location to add transit/shared location flag.
    
    Transit locations are accessible by all users regardless of their
    warehouse assignments, enabling flexible stock movement workflows
    through shared spaces.
    """
    _inherit = "stock.location"
    
    is_transit_location = fields.Boolean(
        string="Transit/Shared Location",
        default=False,
        help="If enabled, this location is accessible by all users for transit operations, "
             "regardless of their warehouse assignments.\n\n"
             "Useful for creating shared spaces where users from different warehouses "
             "can temporarily store or transfer stock without requiring access to each other's warehouses.\n\n"
             "CRITICAL: Must enable this for transit locations. Without it, stock move lines "
             "will be filtered out by Record Rules when picking locations reference transit areas.\n\n"
             "Example: A shared dock location where User1 drops off stock for User2 to pick up."
    )
