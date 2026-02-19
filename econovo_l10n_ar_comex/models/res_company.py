# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


COMEX_SEQUENCE_DEFINITIONS = [
    {
        'name': '%s COMEX Import Operation',
        'code': 'comex.operation.import',
        'prefix': 'IMP/%(year)s/',
        'padding': 5,
    },
    {
        'name': '%s COMEX Export Operation',
        'code': 'comex.operation.export',
        'prefix': 'EXP/%(year)s/',
        'padding': 5,
    },
    {
        'name': '%s COMEX Shipment',
        'code': 'comex.shipment',
        'prefix': 'SHP/%(year)s/',
        'padding': 5,
    },
    {
        'name': '%s COMEX Customs Clearance',
        'code': 'comex.customs.clearance',
        'prefix': 'DSP/%(year)s/',
        'padding': 5,
    },
    {
        'name': '%s COMEX MULC Operation',
        'code': 'comex.mulc',
        'prefix': 'MULC/%(year)s/',
        'padding': 5,
    },
]


class ResCompany(models.Model):
    _inherit = 'res.company'

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------
    comex_default_import_picking_type_id = fields.Many2one(
        'stock.picking.type',
        string="Default COMEX Import Picking Type",
        domain="[('is_comex_import', '=', True), ('company_id', '=', id)]",
        check_company=True,
        help="Default operation type for Purchase Orders created from COMEX "
             "import operations. If not set, the COMEX/IN type is used.",
    )

    # -------------------------------------------------------------------------
    # PRIVATE METHODS
    # -------------------------------------------------------------------------
    def _create_comex_sequences(self):
        """Create COMEX sequences for the given companies.

        Each company gets its own set of sequences for import/export
        operations, shipments, customs clearances, and MULC operations.
        Skips creation if a sequence with the same code already exists
        for the company.
        """
        seq_vals = []
        for company in self:
            existing_codes = set(
                self.env['ir.sequence'].sudo().search([
                    ('company_id', '=', company.id),
                    ('code', 'in', [s['code'] for s in COMEX_SEQUENCE_DEFINITIONS]),
                ]).mapped('code')
            )
            for seq_def in COMEX_SEQUENCE_DEFINITIONS:
                if seq_def['code'] not in existing_codes:
                    seq_vals.append({
                        'name': seq_def['name'] % company.name,
                        'code': seq_def['code'],
                        'prefix': seq_def['prefix'],
                        'padding': seq_def['padding'],
                        'company_id': company.id,
                        'number_next': 1,
                        'number_increment': 1,
                    })
        if seq_vals:
            self.env['ir.sequence'].sudo().create(seq_vals)

    @api.model
    def create_missing_comex_sequences(self):
        """Hook called on module install to create COMEX sequences
        for all existing companies that don't have them yet.

        Also migrates any legacy sequences (company_id set to a specific
        company or without proper company assignment) by keeping them
        for company 1 and creating new ones for other companies.
        """
        companies = self.env['res.company'].sudo().search([])
        companies._create_comex_sequences()

    # -------------------------------------------------------------------------
    # CRUD METHODS
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """Override to create COMEX sequences for new companies."""
        companies = super().create(vals_list)
        companies.sudo()._create_comex_sequences()
        return companies

    # -------------------------------------------------------------------------
    # COMEX STOCK INFRASTRUCTURE
    # -------------------------------------------------------------------------

    # Picking type definitions: (suffix, name, code, sequence_code, sequence)
    COMEX_PICKING_TYPES = [
        ('in', 'Recepciones COMEX', 'incoming', 'COMEX/IN', 1),
        ('arrival', 'Llegadas a Puerto', 'internal', 'COMEX/ARR', 2),
        ('fiscal', 'Depósito Fiscal', 'internal', 'COMEX/FIS', 3),
        ('nationalize', 'Nacionalizaciones', 'internal', 'COMEX/NAC', 4),
    ]

    def _create_comex_stock_infrastructure(self):
        """Create COMEX stock infrastructure (picking types, routes, push rules).

        Locations for company 1 are created via XML data file. This method
        creates the dynamic records that need warehouse references and handles
        additional companies beyond company 1.
        """
        module = 'econovo_l10n_ar_comex'

        for company in self:
            # Check if fully created via XML IDs (records must still exist)
            pt_ref = self.env.ref(
                '%s.comex_picking_type_in_%d' % (module, company.id),
                raise_if_not_found=False,
            )
            route_ref = self.env.ref(
                '%s.comex_route_import_%d' % (module, company.id),
                raise_if_not_found=False,
            )
            if (pt_ref and pt_ref.exists()
                    and route_ref and route_ref.exists()):
                continue

            # Find main warehouse for this company
            warehouse = self.env['stock.warehouse'].sudo().search([
                ('company_id', '=', company.id),
            ], limit=1, order='id')
            if not warehouse:
                continue

            # Get or create COMEX locations for this company
            locations = self._get_or_create_comex_locations(company, module)
            if not locations:
                continue

            loc_in_transit, loc_at_port, loc_fiscal = locations
            main_stock = warehouse.lot_stock_id

            # Create picking types if not already present
            if not (pt_ref and pt_ref.exists()):
                picking_types = self._create_comex_picking_types(
                    company, warehouse, loc_in_transit, loc_at_port,
                    loc_fiscal, main_stock, module,
                )
            else:
                # Rebuild dict from existing XML IDs
                picking_types = {}
                for suffix, _name, _code, _seq_code, _seq in self.COMEX_PICKING_TYPES:
                    ref = self.env.ref(
                        '%s.comex_picking_type_%s_%d' % (module, suffix, company.id),
                        raise_if_not_found=False,
                    )
                    if ref and ref.exists():
                        picking_types[suffix] = ref

            # Create route and push rules if not already present
            if not (route_ref and route_ref.exists()) and len(picking_types) == 4:
                self._create_comex_route_and_rules(
                    company, warehouse, picking_types,
                    loc_in_transit, loc_at_port, loc_fiscal, main_stock,
                )

    def _get_or_create_comex_locations(self, company, module):
        """Get existing COMEX locations or create them for additional companies.

        Company 1 locations are created via XML data. For other companies,
        locations are created programmatically with ir.model.data entries.

        Returns:
            tuple: (loc_in_transit, loc_at_port, loc_fiscal) or False
        """
        Location = self.env['stock.location'].sudo()

        # For the main company, locations come from XML data file
        if company == self.env.ref('base.main_company'):
            loc_in_transit = self.env.ref(
                '%s.comex_location_in_transit' % module,
                raise_if_not_found=False,
            )
            loc_at_port = self.env.ref(
                '%s.comex_location_at_port' % module,
                raise_if_not_found=False,
            )
            loc_fiscal = self.env.ref(
                '%s.comex_location_fiscal_depot' % module,
                raise_if_not_found=False,
            )
            if loc_in_transit and loc_at_port and loc_fiscal:
                return loc_in_transit, loc_at_port, loc_fiscal
            return False

        # For additional companies, create locations with root
        physical_locations = self.env.ref('stock.stock_location_locations')
        comex_root = Location.create({
            'name': _('COMEX Transit'),
            'usage': 'view',
            'location_id': physical_locations.id,
            'company_id': company.id,
        })
        self._ensure_xmlid(module, 'comex_location_root_%d' % company.id,
                           'stock.location', comex_root.id)

        location_defs = [
            ('in_transit', _('En Viaje')),
            ('at_port', _('En Puerto')),
            ('fiscal_depot', _('Depósito Fiscal')),
        ]
        created = []
        for suffix, name in location_defs:
            loc = Location.create({
                'name': name,
                'usage': 'internal',
                'location_id': comex_root.id,
                'company_id': company.id,
            })
            self._ensure_xmlid(module, 'comex_location_%s_%d' % (suffix, company.id),
                               'stock.location', loc.id)
            created.append(loc)

        return tuple(created)

    def _create_comex_picking_types(self, company, warehouse,
                                     loc_in_transit, loc_at_port,
                                     loc_fiscal, main_stock, module):
        """Create COMEX picking types for a company.

        Registers ir.model.data entries so picking types can be referenced
        via XML ID instead of hardcoded sequence_code searches.

        Returns:
            dict: {suffix: picking_type_record}
        """
        PickingType = self.env['stock.picking.type'].sudo()

        # Source/destination per suffix
        location_map = {
            'in': {
                'default_location_dest_id': loc_in_transit.id,
                'show_reserved': False,
            },
            'arrival': {
                'default_location_src_id': loc_in_transit.id,
                'default_location_dest_id': loc_at_port.id,
            },
            'fiscal': {
                'default_location_src_id': loc_at_port.id,
                'default_location_dest_id': loc_fiscal.id,
            },
            'nationalize': {
                'default_location_src_id': loc_fiscal.id,
                'default_location_dest_id': main_stock.id,
            },
        }

        result = {}
        for suffix, name, code, seq_code, sequence in self.COMEX_PICKING_TYPES:
            vals = {
                'name': name,
                'code': code,
                'sequence_code': seq_code,
                'warehouse_id': warehouse.id,
                'company_id': company.id,
                'sequence': sequence,
            }
            vals.update(location_map.get(suffix, {}))
            # All current COMEX picking types are part of the import chain
            vals['is_comex_import'] = True
            pt = PickingType.create(vals)
            self._ensure_xmlid(module, 'comex_picking_type_%s_%d' % (suffix, company.id),
                               'stock.picking.type', pt.id)
            result[suffix] = pt

        return result

    def _create_comex_route_and_rules(self, company, warehouse,
                                       picking_types, loc_in_transit,
                                       loc_at_port, loc_fiscal, main_stock):
        """Create COMEX route and push rules for a company."""
        module = 'econovo_l10n_ar_comex'
        Route = self.env['stock.route'].sudo()
        Rule = self.env['stock.rule'].sudo()

        route = Route.create({
            'name': _('COMEX Import Transit (%s)') % company.name,
            'company_id': company.id,
            'sequence': 100,
        })
        self._ensure_xmlid(module, 'comex_route_import_%d' % company.id,
                           'stock.route', route.id)

        # Associate route with the main warehouse
        warehouse.write({'route_ids': [(4, route.id)]})

        # Push rules: each step chains to the next
        rule_defs = [
            (loc_in_transit, loc_at_port, 'arrival', 1),
            (loc_at_port, loc_fiscal, 'fiscal', 2),
            (loc_fiscal, main_stock, 'nationalize', 3),
        ]
        for loc_src, loc_dest, pt_suffix, sequence in rule_defs:
            rule = Rule.create({
                'name': _('COMEX: %s → %s') % (loc_src.name, loc_dest.name),
                'action': 'push',
                'auto': 'manual',
                'location_src_id': loc_src.id,
                'location_dest_id': loc_dest.id,
                'picking_type_id': picking_types[pt_suffix].id,
                'route_id': route.id,
                'company_id': company.id,
                'propagate_cancel': True,
                'sequence': sequence,
            })
            self._ensure_xmlid(
                module,
                'comex_rule_%s_%d' % (pt_suffix, company.id),
                'stock.rule', rule.id,
            )

    def _ensure_xmlid(self, module, name, model, res_id):
        """Create or update an ir.model.data entry (upsert).

        Handles reinstall scenarios where the XML ID entry may already
        exist from a previous installation but point to a deleted record.
        """
        IrModelData = self.env['ir.model.data'].sudo()
        existing = IrModelData.search([
            ('module', '=', module),
            ('name', '=', name),
        ], limit=1)
        if existing:
            existing.write({'model': model, 'res_id': res_id})
        else:
            IrModelData.create({
                'module': module,
                'name': name,
                'model': model,
                'res_id': res_id,
                'noupdate': True,
            })

    def _get_comex_picking_type(self, step='in'):
        """Get COMEX picking type for this company by logical step.

        Args:
            step: One of 'in', 'arrival', 'fiscal', 'nationalize'

        Returns:
            stock.picking.type record or empty recordset
        """
        self.ensure_one()
        xml_id = 'econovo_l10n_ar_comex.comex_picking_type_%s_%d' % (step, self.id)
        return self.env.ref(xml_id, raise_if_not_found=False) or self.env['stock.picking.type']

    def _get_comex_default_import_picking_type(self):
        """Get the configured default COMEX import picking type.

        Reads the per-company setting first. Falls back to the standard
        COMEX/IN picking type (via XML ID) when no explicit default is set
        or when the configured record is archived/deleted.

        Returns:
            stock.picking.type record or empty recordset
        """
        self.ensure_one()
        pt = self.comex_default_import_picking_type_id
        if pt and pt.exists() and pt.active:
            return pt
        return self._get_comex_picking_type('in')

    @api.model
    def _register_hook(self):
        """Ensure COMEX stock infrastructure exists after module load.

        Runs on both install and update, safe due to XML ID idempotent
        guards in _create_comex_stock_infrastructure().
        """
        super()._register_hook()
        self.create_missing_comex_stock_infrastructure()

    @api.model
    def create_missing_comex_stock_infrastructure(self):
        """Create COMEX stock infrastructure for all companies."""
        companies = self.env['res.company'].sudo().search([])
        companies._create_comex_stock_infrastructure()
