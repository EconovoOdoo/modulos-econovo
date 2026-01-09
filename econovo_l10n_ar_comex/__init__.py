# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import SUPERUSER_ID, api

from . import models


def _post_init_hook(env):
    """Post-installation hook to set up COMEX locations and picking types."""
    # Ensure COMEX location hierarchy is properly configured
    comex_root = env.ref('econovo_l10n_ar_comex.comex_location_root', raise_if_not_found=False)
    if comex_root:
        # Ensure parent locations don't have company restriction
        comex_root.write({'company_id': False})
        child_views = env['stock.location'].search([
            ('location_id', 'child_of', comex_root.id),
            ('usage', '=', 'view'),
        ])
        child_views.write({'company_id': False})

    # Create COMEX picking types for each company
    _create_comex_picking_types(env)


def _create_comex_picking_types(env):
    """Create COMEX picking types and push rules for all companies."""
    companies = env['res.company'].search([])
    for company in companies:
        _create_comex_picking_types_for_company(env, company)


def _create_comex_picking_types_for_company(env, company):
    """Create COMEX picking types and rules for a specific company."""
    # Get references to COMEX locations (global, no company)
    loc_in_transit_sea = env.ref('econovo_l10n_ar_comex.comex_location_in_transit_sea', raise_if_not_found=False)
    loc_port_bsas = env.ref('econovo_l10n_ar_comex.comex_location_port_bsas', raise_if_not_found=False)
    loc_fiscal = env.ref('econovo_l10n_ar_comex.comex_location_fiscal_exolgan', raise_if_not_found=False)
    loc_supplier = env.ref('stock.stock_location_suppliers', raise_if_not_found=False)

    # Get the main warehouse for this company
    warehouse = env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
    if not warehouse:
        return

    lot_stock = warehouse.lot_stock_id

    # Get COMEX route
    comex_route = env.ref('econovo_l10n_ar_comex.route_comex_import', raise_if_not_found=False)

    PickingType = env['stock.picking.type'].sudo()
    StockRule = env['stock.rule'].sudo()

    # Check if COMEX picking types already exist for this company
    comex_in = PickingType.search([
        ('sequence_code', '=', 'COMEX/IN'),
        ('company_id', '=', company.id),
    ], limit=1)
    comex_arrival = PickingType.search([
        ('sequence_code', '=', 'COMEX/ARR'),
        ('company_id', '=', company.id),
    ], limit=1)
    comex_fiscal = PickingType.search([
        ('sequence_code', '=', 'COMEX/FIS'),
        ('company_id', '=', company.id),
    ], limit=1)
    comex_nationalize = PickingType.search([
        ('sequence_code', '=', 'COMEX/NAC'),
        ('company_id', '=', company.id),
    ], limit=1)

    # 1. COMEX/IN - Recepción COMEX (Vendor → En Viaje)
    if not comex_in:
        comex_in = PickingType.create({
            'name': 'Recepción COMEX',
            'sequence_code': 'COMEX/IN',
            'code': 'incoming',
            'company_id': company.id,
            'warehouse_id': warehouse.id,
            'default_location_src_id': loc_supplier.id if loc_supplier else False,
            'default_location_dest_id': loc_in_transit_sea.id if loc_in_transit_sea else False,
            'sequence': 100,
            'show_reserved': False,
            'show_operations': True,
        })

    # 2. COMEX/ARR - Llegada a Puerto (En Viaje → Puerto)
    if not comex_arrival:
        comex_arrival = PickingType.create({
            'name': 'Llegada a Puerto',
            'sequence_code': 'COMEX/ARR',
            'code': 'internal',
            'company_id': company.id,
            'warehouse_id': warehouse.id,
            'default_location_src_id': loc_in_transit_sea.id if loc_in_transit_sea else False,
            'default_location_dest_id': loc_port_bsas.id if loc_port_bsas else False,
            'sequence': 101,
        })

    # 3. COMEX/FIS - Ingreso Depósito Fiscal (Puerto → Depósito Fiscal)
    if not comex_fiscal:
        comex_fiscal = PickingType.create({
            'name': 'Ingreso Depósito Fiscal',
            'sequence_code': 'COMEX/FIS',
            'code': 'internal',
            'company_id': company.id,
            'warehouse_id': warehouse.id,
            'default_location_src_id': loc_port_bsas.id if loc_port_bsas else False,
            'default_location_dest_id': loc_fiscal.id if loc_fiscal else False,
            'sequence': 102,
        })

    # 4. COMEX/NAC - Nacionalización (Depósito Fiscal → Stock)
    if not comex_nationalize:
        comex_nationalize = PickingType.create({
            'name': 'Nacionalización',
            'sequence_code': 'COMEX/NAC',
            'code': 'internal',
            'company_id': company.id,
            'warehouse_id': warehouse.id,
            'default_location_src_id': loc_fiscal.id if loc_fiscal else False,
            'default_location_dest_id': lot_stock.id if lot_stock else False,
            'sequence': 103,
        })

    # Create Push Rules if route exists (check each rule individually)
    if comex_route and loc_in_transit_sea and loc_port_bsas and loc_fiscal and lot_stock:
        # Rule 1: En Viaje → Puerto
        existing_rule1 = StockRule.search([
            ('route_id', '=', comex_route.id),
            ('location_src_id', '=', loc_in_transit_sea.id),
            ('company_id', '=', company.id),
        ], limit=1)
        if not existing_rule1:
            StockRule.create({
                'name': 'COMEX: En Viaje → Puerto',
                'route_id': comex_route.id,
                'location_src_id': loc_in_transit_sea.id,
                'location_dest_id': loc_port_bsas.id,
                'action': 'push',
                'auto': 'manual',
                'picking_type_id': comex_arrival.id,
                'company_id': company.id,
                'warehouse_id': warehouse.id,
            })

        # Rule 2: Puerto → Depósito Fiscal
        existing_rule2 = StockRule.search([
            ('route_id', '=', comex_route.id),
            ('location_src_id', '=', loc_port_bsas.id),
            ('company_id', '=', company.id),
        ], limit=1)
        if not existing_rule2:
            StockRule.create({
                'name': 'COMEX: Puerto → Depósito Fiscal',
                'route_id': comex_route.id,
                'location_src_id': loc_port_bsas.id,
                'location_dest_id': loc_fiscal.id,
                'action': 'push',
                'auto': 'manual',
                'picking_type_id': comex_fiscal.id,
                'company_id': company.id,
                'warehouse_id': warehouse.id,
            })

        # Rule 3: Depósito Fiscal → Stock (Nacionalización)
        existing_rule3 = StockRule.search([
            ('route_id', '=', comex_route.id),
            ('location_src_id', '=', loc_fiscal.id),
            ('company_id', '=', company.id),
        ], limit=1)
        if not existing_rule3:
            StockRule.create({
                'name': 'COMEX: Depósito Fiscal → Stock',
                'route_id': comex_route.id,
                'location_src_id': loc_fiscal.id,
                'location_dest_id': lot_stock.id,
                'action': 'push',
                'auto': 'manual',
                'picking_type_id': comex_nationalize.id,
                'company_id': company.id,
                'warehouse_id': warehouse.id,
            })
