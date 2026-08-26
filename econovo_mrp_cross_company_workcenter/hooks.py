# -*- coding: utf-8 -*-

# Widens hr's own multi-company employee rules so that an employee explicitly
# listed as an allowed employee on a work center of one of the reader's
# companies stays readable, even though the employee record itself belongs to
# another company of the group. Without this, every OTHER user of that company
# (planners, supervisors) hits an AccessError merely by opening a manufacturing
# order or work order showing who is allowed on / working at that work center.
#
# Both rules are global (no groups), so they are ANDed into every check on
# their model: a new rule could only restrict further, never widen. Editing
# their domain is the only way to allow this. It grants strictly what the work
# center configuration already authorizes, and no access to any other record of
# the other company.
_EMPLOYEE_OR_ALLOWED_ON_OWN_COMPANY_WORKCENTER = (
    "['|', ('company_id', 'in', company_ids + [False]),"
    " ('workcenter_ids.company_id', 'in', company_ids)]"
)

WIDENED_EMPLOYEE_RULE_DOMAINS = {
    'hr.hr_employee_comp_rule': _EMPLOYEE_OR_ALLOWED_ON_OWN_COMPANY_WORKCENTER,
    'hr.hr_employee_public_comp_rule': _EMPLOYEE_OR_ALLOWED_ON_OWN_COMPANY_WORKCENTER,
}

# Domains exactly as shipped by hr/security/hr_security.xml. This module
# widens them; uninstalling it must not leave the widened version behind,
# since these rules belong to hr.
_CORE_EMPLOYEE_RULE_DOMAINS = {
    'hr.hr_employee_comp_rule': "[('company_id', 'in', company_ids + [False])]",
    'hr.hr_employee_public_comp_rule': "[('company_id', 'in', company_ids + [False])]",
}


def uninstall_hook(env):
    for xml_id, domain_force in _CORE_EMPLOYEE_RULE_DOMAINS.items():
        rule = env.ref(xml_id, raise_if_not_found=False)
        if rule:
            rule.domain_force = domain_force
