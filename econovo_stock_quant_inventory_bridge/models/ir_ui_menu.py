# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def _register_hook(self):
        super()._register_hook()
        # stock_inventory archives the core "Physical Inventory" menu through
        # a data record that is not wrapped in noupdate="1" (see its
        # stock_inventory.xml), so it gets re-hidden every time that module
        # is upgraded. Re-activating it here instead of only through XML
        # data makes the fix self-healing on every registry reload (server
        # restart or any module update), regardless of whether this module
        # happens to be part of that particular upgrade.
        menu = self.env.ref(
            'stock.menu_action_inventory_tree', raise_if_not_found=False
        )
        if menu and not menu.active:
            menu.sudo().active = True
        return
