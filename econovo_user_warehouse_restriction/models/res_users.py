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


class ResUsers(models.Model):
    """Extends res.users to add cross-warehouse transfer permission.
    
    This field allows administrators to grant specific users the ability
    to transfer stock between warehouses they don't have explicit access to,
    providing flexibility while maintaining overall warehouse restrictions.
    """
    _inherit = 'res.users'
    
    allow_cross_warehouse_transfers = fields.Boolean(
        string="Allow Cross-Warehouse Transfers",
        default=False,
        help="If enabled, this user can transfer stock to warehouses outside their assigned list.\n\n"
             "This permission bypasses destination warehouse restrictions while still respecting "
             "source warehouse limitations.\n\n"
             "Use case: Regional managers who need to redistribute stock across multiple warehouses "
             "without having full access to each warehouse's inventory."
    )
