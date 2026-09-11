# -*- coding: utf-8 -*-

# Widens room's own multi-company office/room rules so that an office left
# without a company (``company_id`` is now optional, see
# ``models/room_office.py``) -- and its rooms, through their own related
# ``company_id`` -- stays visible/bookable by every company, instead of
# only whichever one happens to own it.
#
# Both rules are global (no groups), so they are ANDed into every check on
# their model: a new rule could only restrict further, never widen. Editing
# their domain is the only way to allow this.
_OFFICE_OR_ROOM_SHARED_WITH_ALL_COMPANIES = (
    "['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]"
)

WIDENED_ROOM_RULE_DOMAINS = {
    'room.room_office_comp_rule': _OFFICE_OR_ROOM_SHARED_WITH_ALL_COMPANIES,
    'room.room_room_comp_rule': _OFFICE_OR_ROOM_SHARED_WITH_ALL_COMPANIES,
}

# Domains exactly as shipped by room/security/ir_rule.xml. This module
# widens them; uninstalling it must not leave the widened version behind,
# since these rules belong to room and company_id becomes required again
# once this module is gone.
_CORE_ROOM_RULE_DOMAINS = {
    'room.room_office_comp_rule': "[('company_id', 'in', company_ids)]",
    'room.room_room_comp_rule': "[('company_id', 'in', company_ids)]",
}


def uninstall_hook(env):
    for xml_id, domain_force in _CORE_ROOM_RULE_DOMAINS.items():
        rule = env.ref(xml_id, raise_if_not_found=False)
        if rule:
            rule.domain_force = domain_force
