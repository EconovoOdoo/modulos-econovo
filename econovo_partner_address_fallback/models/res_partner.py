# -*- coding: utf-8 -*-
from odoo import models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def address_get(self, adr_pref=None):
        """Override to fall back to the commercial partner (top-level company)
        instead of the individual contact when no explicit address of the
        requested type exists in the partner hierarchy.

        Standard Odoo behaviour: if no ``type='invoice'`` (or ``'delivery'``)
        child is found under the company, ``address_get`` falls back to
        ``result['contact']``, which for an individual with ``type='contact'``
        is the individual itself.  This means invoices and pickings end up
        addressed to the person rather than the company.

        This override corrects that: after the standard resolution, any
        non-``'contact'`` address type that still points to the individual
        contact is re-routed to ``commercial_partner_id``.

        Conditions that trigger the override (all must be true):
          - ``self`` is a single-record set (multi-record calls are rare and
            deliberately left unchanged to avoid unintended side-effects).
          - The partner is not a company (``is_company == False``).
          - The partner has a ``parent_id`` (i.e. belongs to a company).
          - ``commercial_partner_id`` differs from ``self`` (sanity check).
          - The resolved id for the address type equals ``self.id``, meaning the
            standard logic found no explicit address child and fell back to the
            individual.
        """
        result = super().address_get(adr_pref)

        adr_pref_set = set(adr_pref or [])
        if (
            len(self) == 1
            and not self.is_company
            and self.parent_id
            and self.commercial_partner_id != self
        ):
            commercial_id = self.commercial_partner_id.id
            for adr_type in adr_pref_set - {'contact'}:
                if result.get(adr_type) == self.id:
                    result[adr_type] = commercial_id

        return result
