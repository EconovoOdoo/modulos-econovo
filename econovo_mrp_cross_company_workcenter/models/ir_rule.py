# -*- coding: utf-8 -*-
from odoo import models

from ..hooks import WIDENED_EMPLOYEE_RULE_DOMAINS


class IrRule(models.Model):
    _inherit = 'ir.rule'

    def _register_hook(self):
        # hr ships these rules under noupdate="1", so a plain data <record>
        # here would be silently skipped on upgrade. Re-assert them on every
        # registry load instead, which also self-heals if they get reverted in
        # the database.
        super()._register_hook()
        for xml_id, domain_force in WIDENED_EMPLOYEE_RULE_DOMAINS.items():
            rule = self.env.ref(xml_id, raise_if_not_found=False)
            if rule and rule.domain_force != domain_force:
                rule.domain_force = domain_force
