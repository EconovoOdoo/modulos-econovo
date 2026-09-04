# -*- coding: utf-8 -*-
from odoo import models


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    def _get_multilevel_bom_ids(self):
        """Return this BOM (or these BOMs) plus every sub-BOM used by their components, at any depth."""
        bom_ids = set()
        boms_to_explode = self
        while boms_to_explode:
            new_boms = boms_to_explode.filtered(lambda bom: bom.id not in bom_ids)
            bom_ids.update(new_boms.ids)
            boms_to_explode = new_boms.bom_line_ids.child_bom_id
        return list(bom_ids)
