# -*- coding: utf-8 -*-
# Copyright 2026 Jose D. Leonett
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).


def post_init_hook(env):
    """Seed workcenter_id from the Studio field it replaces, if present."""
    if 'x_studio_workcenter_id' not in env['stock.picking']._fields:
        return
    env.cr.execute(
        "UPDATE stock_picking SET workcenter_id = x_studio_workcenter_id "
        "WHERE x_studio_workcenter_id IS NOT NULL"
    )
