# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    """Extend settings to add COMEX tribute invoice configuration."""
    
    _inherit = 'res.config.settings'
    
    # Stock / Picking Type Settings
    comex_default_import_picking_type_id = fields.Many2one(
        'stock.picking.type',
        string="Default COMEX Import Picking Type",
        related='company_id.comex_default_import_picking_type_id',
        readonly=False,
        domain="[('is_comex_import', '=', True)]",
    )

    # Tribute Invoice Settings
    comex_auto_prefill_invoice = fields.Boolean(
        string="Auto-fill Tribute Invoice Lines",
        config_parameter='econovo_l10n_ar_comex.auto_prefill_invoice',
        help="When creating tribute invoice from clearance, automatically pre-fill lines with tribute amounts",
    )
    
    comex_default_tribute_vendor_id = fields.Many2one(
        'res.partner',
        string="Default Tribute Vendor",
        config_parameter='econovo_l10n_ar_comex.default_tribute_vendor_id',
        domain="[('supplier_rank', '>', 0)]",
        help="Default vendor when creating tribute invoices (e.g., AFIP, Customs Broker)",
    )
    
    comex_default_tribute_doc_type_id = fields.Many2one(
        'l10n_latam.document.type',
        string="Default Tribute Doc Type",
        config_parameter='econovo_l10n_ar_comex.default_tribute_doc_type_id',
        domain="[('country_id.code', '=', 'AR'), ('internal_type', '=', 'invoice')]",
        help="Default document type for tribute invoices (e.g., Type 66 - Import Clearance)",
    )
    
    comex_tribute_line_filter = fields.Selection(
        selection=[
            ('all', 'All Non-Zero Tributes'),
            ('selected', 'Only Selected Tributes'),
        ],
        string="Invoice Lines to Include",
        config_parameter='econovo_l10n_ar_comex.tribute_line_filter',
        default='all',
        help="Which tribute amounts to include in invoice lines",
    )
    
    comex_tribute_line_config_ids = fields.Many2many(
        'comex.tribute.invoice.line.config',
        string="Tributes to Include",
        compute='_compute_tribute_line_config_ids',
        inverse='_inverse_tribute_line_config_ids',
        help="Configure which tribute fields should be included as invoice lines (only if 'Only Selected' is chosen above)",
    )
    
    @api.depends('company_id')
    def _compute_tribute_line_config_ids(self):
        """Load tribute line configurations for current company."""
        for record in self:
            if record.company_id:
                configs = self.env['comex.tribute.invoice.line.config'].search([
                    ('company_id', '=', record.company_id.id)
                ])
                record.comex_tribute_line_config_ids = configs
            else:
                record.comex_tribute_line_config_ids = False
    
    def _inverse_tribute_line_config_ids(self):
        """Save changes to tribute line configurations."""
        for record in self:
            if not record.company_id:
                continue
            
            # Get current configs for this company
            existing_configs = self.env['comex.tribute.invoice.line.config'].search([
                ('company_id', '=', record.company_id.id)
            ])
            
            # Compute difference
            to_remove = existing_configs - record.comex_tribute_line_config_ids
            to_add = record.comex_tribute_line_config_ids - existing_configs
            
            # Remove old configs
            to_remove.unlink()
            
            # Update company_id for new configs
            for config in to_add:
                if not config.company_id or config.company_id.id != record.company_id.id:
                    config.company_id = record.company_id
