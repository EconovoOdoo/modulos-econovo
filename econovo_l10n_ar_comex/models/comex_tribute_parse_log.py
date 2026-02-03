# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ComexTributeParseLog(models.Model):
    """Audit log for tribute parsing.
    
    Records every invoice line parsing attempt, whether matched or unmatched.
    Provides full traceability for debugging and configuration refinement.
    """
    
    _name = 'comex.tribute.parse.log'
    _description = 'COMEX Tribute Parse Log'
    _order = 'create_date desc'
    _rec_name = 'invoice_line_id'
    
    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------
    customs_clearance_id = fields.Many2one(
        'comex.customs.clearance',
        string="Customs Clearance",
        required=True,
        ondelete='cascade',
        index=True,
    )
    invoice_id = fields.Many2one(
        'account.move',
        string="Invoice",
        required=True,
        index=True,
    )
    invoice_line_id = fields.Many2one(
        'account.move.line',
        string="Invoice Line",
        required=True,
    )
    
    # Match result
    matched_by = fields.Selection(
        selection=[
            ('product', 'Product Mapping'),
            ('keyword', 'Keyword Mapping'),
            ('manual', 'Manual Override'),
            ('unmatched', 'Unmatched'),
        ],
        string="Matched By",
        required=True,
        help="How this line was matched:\n"
             "- Product Mapping: Matched by product_id\n"
             "- Keyword Mapping: Matched by text pattern\n"
             "- Manual Override: Manually corrected by user\n"
             "- Unmatched: No mapping found",
    )
    mapping_record = fields.Char(
        string="Mapping Used",
        help="Reference to mapping record (e.g., 'comex.tribute.product.mapping,5')",
    )
    tribute_field = fields.Char(
        string="Target Field",
        help="Field name where amount was accumulated (e.g., 'amount_duties')",
    )
    
    # Amounts
    amount_parsed = fields.Monetary(
        string="Amount Parsed",
        currency_field='currency_id',
        help="Amount extracted from this line",
    )
    currency_id = fields.Many2one(
        'res.currency',
        string="Currency",
    )
    
    # Snapshots (for audit trail)
    line_description = fields.Text(
        string="Line Description",
        help="Snapshot of invoice line description at parse time",
    )
    product_name = fields.Char(
        string="Product Name",
        help="Snapshot of product name at parse time (if any)",
    )
