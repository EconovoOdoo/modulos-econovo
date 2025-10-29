# -*- coding: utf-8 -*-

import logging
from collections import defaultdict
from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.tools import float_compare

_logger = logging.getLogger(__name__)


class StockRule(models.Model):
    _inherit = "stock.rule"

    def _run_manufacture(self, procurements):
        """Enhanced version with configurable draft behavior.
        
        Maintains all Odoo native logic:
        - Quantity validation (negative quantities)
        - MO consolidation for non-MTO flows
        - Message posting (traceability in chatter)
        - Standard _should_auto_confirm_procurement_mo filter
        
        Adds configurable auto-confirm based on hierarchy:
        1. Global settings (res.config.settings)
        2. Product settings (product.template) - overrides global
        3. User settings (res.users) - overrides product
        
        Each level can configure independently for:
        - MTO (Make To Order from Sales)
        - MTS (Make To Stock replenishment)
        - MPS (Master Production Schedule)
        - Orderpoint (Reordering Rules)
        """
        _logger.info("="*80)
        _logger.info("ECONOVO DRAFT MTO/MO: _run_manufacture called with %d procurements", len(procurements))
        
        new_productions_values_by_company = defaultdict(list)
        
        # Phase 1: Prepare MO values (Odoo native logic)
        for procurement, rule in procurements:
            # Validate quantity (Odoo native - prevent negative quantities)
            if float_compare(
                procurement.product_qty, 0, 
                precision_rounding=procurement.product_uom.rounding
            ) <= 0:
                continue
            
            bom = rule._get_matching_bom(
                procurement.product_id, 
                procurement.company_id, 
                procurement.values
            )

            # Try to consolidate MO (Odoo native logic - only for non-MTO)
            mo = self.env['mrp.production']
            mto_route = self.env['stock.warehouse']._find_global_route(
                'stock.route_warehouse0_mto', 
                _('Replenish on Order (MTO)')
            )
            
            if rule.route_id != mto_route and procurement.origin != 'MPS':
                domain = rule._make_mo_get_domain(procurement, bom)
                mo = self.env['mrp.production'].sudo().search(domain, limit=1)
            
            if not mo:
                # Create new MO
                new_productions_values_by_company[procurement.company_id.id].append(
                    rule._prepare_mo_vals(*procurement, bom)
                )
            else:
                # Consolidate into existing MO (Odoo native logic)
                self.env['change.production.qty'].sudo().with_context(
                    skip_activity=True
                ).create({
                    'mo_id': mo.id,
                    'product_qty': mo.product_id.uom_id._compute_quantity(
                        (mo.product_uom_qty + procurement.product_qty), 
                        mo.product_uom_id
                    )
                }).change_prod_qty()

        # Phase 2: Create MOs and conditionally confirm
        note_subtype_id = self.env['ir.model.data']._xmlid_to_res_id('mail.mt_note')
        
        for company_id, productions_values in new_productions_values_by_company.items():
            # Create MOs (as SUPERUSER like Odoo native)
            productions = self.env['mrp.production'].with_user(
                SUPERUSER_ID
            ).sudo().with_company(company_id).create(productions_values)
            
            # NEW: Determine which MOs should be confirmed based on configuration
            productions_to_confirm = self.env['mrp.production']
            
            for production in productions:
                # Find corresponding procurement
                procurement, rule = self._find_procurement_for_mo(
                    production, procurements
                )
                
                if procurement and rule:
                    # Check if should stay in draft (NEW LOGIC)
                    should_stay_draft = self._should_keep_mo_draft(
                        procurement, rule, production
                    )
                    
                    _logger.info(
                        "MO %s (Product: %s): should_stay_draft=%s",
                        production.name,
                        production.product_id.name,
                        should_stay_draft
                    )
                    
                    if not should_stay_draft:
                        productions_to_confirm |= production
                else:
                    _logger.warning(
                        "MO %s: Could not find corresponding procurement! Will auto-confirm.",
                        production.name
                    )
                    productions_to_confirm |= production
            
            _logger.info(
                "Total MOs created: %d, MOs to confirm: %d, MOs staying draft: %d",
                len(productions),
                len(productions_to_confirm),
                len(productions) - len(productions_to_confirm)
            )
            
            # Confirm selected MOs (using Odoo's native filter)
            productions_to_confirm.filtered(
                self._should_auto_confirm_procurement_mo
            ).action_confirm()
            
            # Phase 3: Post messages (Odoo native traceability logic)
            for production in productions:
                origin_production = (
                    production.move_dest_ids and 
                    production.move_dest_ids[0].raw_material_production_id or 
                    False
                )
                orderpoint = production.orderpoint_id
                
                if orderpoint and orderpoint.create_uid.id == SUPERUSER_ID and orderpoint.trigger == 'manual':
                    production.message_post(
                        body=_('This production order has been created from Replenishment Report.'),
                        message_type='comment',
                        subtype_id=note_subtype_id
                    )
                elif orderpoint:
                    production.message_post_with_source(
                        'mail.message_origin_link',
                        render_values={'self': production, 'origin': orderpoint},
                        subtype_id=note_subtype_id,
                    )
                elif origin_production:
                    production.message_post_with_source(
                        'mail.message_origin_link',
                        render_values={'self': production, 'origin': origin_production},
                        subtype_id=note_subtype_id,
                    )
        
        return True

    def _find_procurement_for_mo(self, production, procurements):
        """Find the procurement that generated this MO.
        
        Args:
            production (mrp.production): The created Manufacturing Order
            procurements (list): List of (procurement, rule) tuples
            
        Returns:
            tuple: (procurement, rule) or (None, None) if not found
        """
        for procurement, rule in procurements:
            if (procurement.product_id == production.product_id and 
                procurement.company_id == production.company_id):
                return procurement, rule
        return None, None

    def _should_keep_mo_draft(self, procurement, rule, production):
        """Determine if MO should stay in draft.
        
        Hierarchy: Global → Product → User
        Each level can override the previous one.
        
        Args:
            procurement: Procurement object with product, values, origin
            rule (stock.rule): Stock rule that triggered the MO
            production (mrp.production): The created Manufacturing Order
            
        Returns:
            bool: True if MO should stay in draft, False to auto-confirm
        """
        source_type = self._get_procurement_source_type(procurement, rule)
        
        _logger.info(
            "Checking draft policy for MO %s - Source Type: %s",
            production.name,
            source_type
        )
        
        # 1. Start with GLOBAL settings
        draft_decision = self._get_global_draft_decision(source_type)
        _logger.info("  -> Global decision: %s", draft_decision)
        
        # 2. Override with PRODUCT settings (if configured)
        product = procurement.product_id.product_tmpl_id
        if product.mo_draft_policy != 'use_global':
            draft_decision = self._get_product_draft_decision(
                product, source_type
            )
            _logger.info(
                "  -> Product '%s' overrides with policy '%s': %s",
                product.name,
                product.mo_draft_policy,
                draft_decision
            )
        
        # 3. Final override with USER settings (if configured)
        user = self.env.user
        if user.mo_draft_policy != 'use_global':
            draft_decision = self._get_user_draft_decision(
                user, source_type
            )
            _logger.info(
                "  -> User '%s' overrides with policy '%s': %s",
                user.name,
                user.mo_draft_policy,
                draft_decision
            )
        
        _logger.info("  -> FINAL DECISION: %s", draft_decision)
        
        return draft_decision

    def _get_procurement_source_type(self, procurement, rule):
        """Identify the source type of procurement.
        
        Detection logic (in order of priority):
        1. MTO: From sales order (has sale_line_id or is MTO route)
        2. MPS: From Master Production Schedule (origin == 'MPS')
        3. Orderpoint: From reordering rules (has orderpoint_id)
        4. MTS: Default for everything else (stock replenishment)
        
        Args:
            procurement: Procurement object
            rule (stock.rule): Stock rule
            
        Returns:
            str: 'mto', 'mts', 'mps', or 'orderpoint'
        """
        values = procurement.values
        
        # Detect MTO route
        mto_route = self.env['stock.warehouse']._find_global_route(
            'stock.route_warehouse0_mto', 
            _('Replenish on Order (MTO)')
        )
        
        _logger.debug(
            "Detecting source type - Rule: %s, MTO Route: %s, Origin: %s, Values keys: %s",
            rule.route_id.name if rule.route_id else "No route",
            mto_route.name if mto_route else "Not found",
            procurement.origin,
            list(values.keys()) if values else []
        )
        
        # Priority order for detection:
        if rule.route_id == mto_route or values.get('sale_line_id'):
            _logger.debug("  -> Detected as MTO")
            return 'mto'
        elif procurement.origin == 'MPS':
            _logger.debug("  -> Detected as MPS")
            return 'mps'
        elif values.get('orderpoint_id'):
            _logger.debug("  -> Detected as Orderpoint")
            return 'orderpoint'
        else:
            _logger.debug("  -> Detected as MTS (default)")
            return 'mts'

    def _get_global_draft_decision(self, source_type):
        """Get draft decision from global settings.
        
        Reads from system parameters configured in Settings.
        
        Args:
            source_type (str): 'mto', 'mts', 'mps', 'orderpoint'
            
        Returns:
            bool: True if should stay draft, False to auto-confirm
        """
        config = self.env['ir.config_parameter'].sudo()
        policy = config.get_param('econovo_draft_mto_mo.global_policy', 'native_flow')
        
        if policy == 'always_draft':
            return True
        elif policy == 'native_flow':
            return False  # Let Odoo's native logic decide (_should_auto_confirm_procurement_mo)
        elif policy == 'custom':
            # Check specific source type setting
            param_map = {
                'mto': 'econovo_draft_mto_mo.draft_for_mto',
                'mts': 'econovo_draft_mto_mo.draft_for_mts',
                'mps': 'econovo_draft_mto_mo.draft_for_mps',
                'orderpoint': 'econovo_draft_mto_mo.draft_for_orderpoint',
            }
            param_key = param_map.get(source_type)
            if param_key:
                return config.get_param(param_key, 'False') == 'True'
        
        return False

    def _get_product_draft_decision(self, product, source_type):
        """Get draft decision from product settings.
        
        Product can override global settings.
        
        Args:
            product (product.template): Product template record
            source_type (str): 'mto', 'mts', 'mps', 'orderpoint'
            
        Returns:
            bool: True if should stay draft, False to auto-confirm
        """
        if product.mo_draft_policy == 'always_draft':
            return True
        elif product.mo_draft_policy == 'always_confirm':
            return False
        elif product.mo_draft_policy == 'native_flow':
            return False  # Let Odoo's native logic decide
        elif product.mo_draft_policy == 'custom':
            # Check specific source type setting
            field_map = {
                'mto': 'mo_draft_mto',
                'mts': 'mo_draft_mts',
                'mps': 'mo_draft_mps',
                'orderpoint': 'mo_draft_orderpoint',
            }
            field_name = field_map.get(source_type)
            if field_name:
                return getattr(product, field_name, False)
        
        # 'use_global' - fallback to global settings
        return self._get_global_draft_decision(source_type)

    def _get_user_draft_decision(self, user, source_type):
        """Get draft decision from user settings.
        
        User can override product and global settings.
        
        Args:
            user (res.users): User record
            source_type (str): 'mto', 'mts', 'mps', 'orderpoint'
            
        Returns:
            bool: True if should stay draft, False to auto-confirm
        """
        if user.mo_draft_policy == 'always_draft':
            return True
        elif user.mo_draft_policy == 'always_confirm':
            return False
        elif user.mo_draft_policy == 'native_flow':
            return False  # Let Odoo's native logic decide
        elif user.mo_draft_policy == 'custom':
            # Check specific source type setting
            field_map = {
                'mto': 'mo_draft_mto',
                'mts': 'mo_draft_mts',
                'mps': 'mo_draft_mps',
                'orderpoint': 'mo_draft_orderpoint',
            }
            field_name = field_map.get(source_type)
            if field_name:
                return getattr(user, field_name, False)
        
        # This shouldn't happen if called correctly (policy != 'use_global')
        # But fallback to product/global chain
        product = self.env.context.get('active_product')
        if product:
            return self._get_product_draft_decision(product, source_type)
        return self._get_global_draft_decision(source_type)
