# -*- coding: utf-8 -*-
from odoo import models

from ..hooks import WIDENED_ROOM_RULE_DOMAINS


class IrRule(models.Model):
    _inherit = 'ir.rule'

    def _register_hook(self):
        # room does not ship these rules under noupdate, but re-asserting
        # them on every registry load keeps this self-healing (e.g. if a
        # Studio edit or a future room upgrade ever resets their domain).
        super()._register_hook()
        for xml_id, domain_force in WIDENED_ROOM_RULE_DOMAINS.items():
            rule = self.env.ref(xml_id, raise_if_not_found=False)
            if rule and rule.domain_force != domain_force:
                rule.domain_force = domain_force
