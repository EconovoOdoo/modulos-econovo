# -*- coding: utf-8 -*-
# Part of Econovo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


class ComexOperationReportLine(models.Model):
    """Line-grained analysis of COMEX operations.

    One row per COMEX product line, carrying every parent operation column, plus
    one synthetic row per operation that has no product line at all (so those
    operations are not lost from the analysis).
    """

    _name = 'comex.operation.report.line'
    _description = 'COMEX Operation Line Analysis'
    _order = 'date_operation desc, operation_name desc, sequence, id'
    _rec_name = 'operation_name'
    _auto = False
    _depends = {
        'comex.operation': [
            'active', 'name', 'operation_type', 'stage_id', 'color', 'partner_id',
            'date_operation', 'date_etd', 'date_eta', 'date_arrival',
            'transport_mode', 'origin_country_id', 'container_total_count',
            'payment_terms_display', 'nominated_bank_id',
            'commercial_payment_status', 'customs_payment_status',
            'purchase_order_payment_status', 'sale_order_payment_status',
            'company_id', 'currency_id', 'currency_ars_id', 'currency_usd_id',
            'currency_rate', 'currency_mismatch', 'vep_amount', 'amount_fob',
            'amount_fob_usd', 'amount_cif',
        ],
        'comex.operation.product.line': [
            'operation_id', 'sequence', 'product_id', 'product_tmpl_id',
            'product_uom', 'product_qty', 'qty_received', 'qty_delivered',
            'price_unit', 'price_unit_usd', 'price_subtotal', 'price_subtotal_usd',
            'origin_currency_id', 'origin_type', 'purchase_order_id', 'sale_order_id',
            'current_location_display', 'lot_name_display', 'last_delivery_partner_id',
        ],
        'comex.shipment': ['operation_id', 'name', 'active'],
        'res.company': ['currency_id'],
    }

    # -------------------------------------------------------------------------
    # FIELDS
    # -------------------------------------------------------------------------
    # Grain
    operation_id = fields.Many2one(
        'comex.operation',
        string="COMEX Operation",
        readonly=True,
    )
    product_line_id = fields.Many2one(
        'comex.operation.product.line',
        string="Product Line",
        readonly=True,
    )
    has_product_line = fields.Boolean(
        string="Has Product Line",
        readonly=True,
        help="Unchecked on operations that have no product line at all.",
    )
    sequence = fields.Integer(readonly=True, group_operator=None)
    active = fields.Boolean(readonly=True)

    # Operation header
    operation_name = fields.Char(
        string="COMEX Reference",
        readonly=True,
    )
    operation_type = fields.Selection(
        selection=[
            ('import', 'Import'),
            ('export', 'Export'),
        ],
        string="Operation Type",
        readonly=True,
    )
    stage_id = fields.Many2one(
        'comex.operation.stage',
        string="Stage",
        readonly=True,
    )
    color = fields.Integer(
        string="Color Index",
        readonly=True,
        group_operator=None,
        help="Color of the parent operation. Read-only here: open the operation to change it.",
    )
    partner_id = fields.Many2one(
        'res.partner',
        string="Supplier/Customer",
        readonly=True,
    )
    date_operation = fields.Date(
        string="Operation Date",
        readonly=True,
    )
    date_etd = fields.Date(
        string="ETD",
        readonly=True,
    )
    date_eta = fields.Date(
        string="ETA",
        readonly=True,
    )
    date_arrival = fields.Date(
        string="Actual Arrival Date",
        readonly=True,
    )
    transport_mode = fields.Selection(
        selection=[
            ('sea', 'Sea'),
            ('air', 'Air'),
            ('land', 'Land'),
            ('multimodal', 'Multimodal'),
        ],
        string="Transport Mode",
        readonly=True,
    )
    origin_country_id = fields.Many2one(
        'res.country',
        string="Origin Country",
        readonly=True,
    )
    container_total_count = fields.Integer(
        string="Total Containers",
        readonly=True,
        group_operator=None,
        help="Container count of the parent operation, repeated on every line of that "
             "operation. Not aggregated, since summing it would multiply it by the "
             "number of lines.",
    )
    bl_numbers = fields.Char(
        string="BL Numbers",
        readonly=True,
    )
    payment_terms_display = fields.Char(
        string="Payment Terms",
        readonly=True,
    )
    nominated_bank_id = fields.Many2one(
        'res.partner',
        string="Nominated Bank",
        readonly=True,
    )
    commercial_payment_status = fields.Selection(
        selection=[
            ('not_paid', 'Not Paid'),
            ('partial', 'Partially Paid'),
            ('in_payment', 'Paid (Pending Reconciliation)'),
            ('paid', 'Fully Paid'),
        ],
        string="Commercial Payment Status",
        readonly=True,
    )
    customs_payment_status = fields.Selection(
        selection=[
            ('not_paid', 'Not Paid'),
            ('partial', 'Partially Paid'),
            ('in_payment', 'Paid (Pending Reconciliation)'),
            ('paid', 'Fully Paid'),
        ],
        string="Customs Payment Status",
        readonly=True,
    )
    purchase_order_payment_status = fields.Selection(
        selection=[
            ('not_paid', 'Not Paid'),
            ('partial', 'Partially Paid'),
            ('in_payment', 'Paid (Pending Reconciliation)'),
            ('paid', 'Fully Paid'),
        ],
        string="Purchase Order Payment Status",
        readonly=True,
    )
    sale_order_payment_status = fields.Selection(
        selection=[
            ('not_paid', 'Not Paid'),
            ('partial', 'Partially Paid'),
            ('in_payment', 'Paid (Pending Reconciliation)'),
            ('paid', 'Fully Paid'),
        ],
        string="Sale Order Payment Status",
        readonly=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string="Company",
        readonly=True,
    )
    currency_mismatch = fields.Boolean(
        string="Currency Mismatch",
        readonly=True,
        help="At least one line of this operation comes from a document in a "
             "different currency than the operation's own. FOB amounts are still "
             "correct; Freight/Insurance/CIF are manual and may need a look.",
    )

    # Operation header (not available as SQL columns)
    tag_ids = fields.Many2many(
        'comex.operation.tag',
        string="Tags",
        related='operation_id.tag_ids',
        readonly=True,
    )
    shipment_ids = fields.One2many(
        related='operation_id.shipment_ids',
        string="Shipments",
        readonly=True,
    )
    dispatch_invoice_numbers = fields.Char(
        string="N° Despacho",
        related='operation_id.dispatch_invoice_numbers',
        readonly=True,
    )

    # Stock position (computed on the product line, exposed here)
    current_location_ids = fields.Many2many(
        'stock.location',
        string="Current Locations",
        related='product_line_id.current_location_ids',
        readonly=True,
    )
    current_location_display = fields.Char(
        string="Current Location",
        readonly=True,
    )
    lot_name_display = fields.Char(
        string="Serial Numbers",
        readonly=True,
    )
    last_delivery_partner_id = fields.Many2one(
        'res.partner',
        string="Last Delivery Contact",
        readonly=True,
    )
    lot_ids = fields.Many2many(
        'stock.lot',
        string="Lots/Serial Numbers",
        related='product_line_id.lot_ids',
        readonly=True,
    )
    stock_status = fields.Selection(
        related='product_line_id.stock_status',
        string="Stock Status",
        readonly=True,
    )

    # Currencies
    currency_id = fields.Many2one(
        'res.currency',
        string="Currency",
        readonly=True,
    )
    currency_ars_id = fields.Many2one(
        'res.currency',
        string="ARS Currency",
        readonly=True,
    )
    currency_usd_id = fields.Many2one(
        'res.currency',
        string="USD Currency",
        readonly=True,
    )
    origin_currency_id = fields.Many2one(
        'res.currency',
        string="Origin Currency",
        readonly=True,
    )
    company_currency_id = fields.Many2one(
        'res.currency',
        string="Company Currency",
        readonly=True,
    )

    # Product line
    product_id = fields.Many2one(
        'product.product',
        string="Product",
        readonly=True,
    )
    product_tmpl_id = fields.Many2one(
        'product.template',
        string="Product Template",
        readonly=True,
    )
    product_uom_id = fields.Many2one(
        'uom.uom',
        string="Unit of Measure",
        readonly=True,
    )
    product_qty = fields.Float(
        string="Quantity",
        digits='Product Unit of Measure',
        readonly=True,
    )
    qty_received = fields.Float(
        string="Received Qty",
        digits='Product Unit of Measure',
        readonly=True,
    )
    qty_delivered = fields.Float(
        string="Delivered Qty",
        digits='Product Unit of Measure',
        readonly=True,
    )
    price_unit = fields.Monetary(
        string="FOB Unit Price",
        currency_field='origin_currency_id',
        readonly=True,
        group_operator=None,
        help="Unit price in the currency of the purchase/sale order it comes from. "
             "Not aggregated: a sum of unit prices has no business meaning. Use "
             "FOB Unit Price (USD) or (Company Currency) to compare across lines.",
    )
    price_unit_usd = fields.Monetary(
        string="FOB Unit Price (USD)",
        currency_field='currency_usd_id',
        readonly=True,
        group_operator=None,
        help="Formula: price_unit converted to USD using the exchange rate of the "
             "purchase/sale order this line comes from (its own currency and date).",
    )
    price_unit_company = fields.Monetary(
        string="FOB Unit Price (Company Currency)",
        currency_field='company_currency_id',
        readonly=True,
        group_operator=None,
        help="Formula: price_unit / operation currency rate. Expressed in the "
             "currency of the operation company.",
    )
    price_subtotal = fields.Monetary(
        string="FOB Subtotal",
        currency_field='origin_currency_id',
        readonly=True,
        group_operator=None,
        help="Line subtotal in the currency of the purchase/sale order it comes from. "
             "Not aggregated, because operations may combine lines in different "
             "currencies. Use FOB Subtotal (USD) or Subtotal (Company Currency) to add "
             "up amounts.",
    )
    price_subtotal_usd = fields.Monetary(
        string="FOB Subtotal (USD)",
        currency_field='currency_usd_id',
        readonly=True,
        help="Formula: price_subtotal converted to USD using the exchange rate of the "
             "purchase/sale order this line comes from (its own currency and date). "
             "Always in USD, so it can be safely summed.",
    )
    price_subtotal_company = fields.Monetary(
        string="FOB Subtotal (Company Currency)",
        currency_field='company_currency_id',
        readonly=True,
        help="Formula: price_subtotal / operation currency rate. Expressed in the "
             "currency of the operation company, so it can be safely summed.",
    )
    origin_type = fields.Selection(
        selection=[
            ('purchase', 'Purchase Order'),
            ('sale', 'Sale Order'),
            ('manual', 'Manual Entry'),
        ],
        string="Origin",
        readonly=True,
    )
    purchase_order_id = fields.Many2one(
        'purchase.order',
        string="Purchase Order",
        readonly=True,
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string="Sale Order",
        readonly=True,
    )

    # Header amounts: repeated value (never summed) and prorated share (summed)
    line_share = fields.Float(
        string="Line Share",
        digits=(16, 6),
        readonly=True,
        group_operator=None,
        help="Weight of this line inside its operation, used to prorate the operation "
             "amounts.\n"
             "Formula: line subtotal / total subtotal of the operation.\n"
             "If that total is zero or negative, the split is equal: 1 / number of "
             "lines of the operation.\n"
             "An operation without lines has a single row with a share of 1.\n"
             "The shares of one operation always add up to 1.",
    )
    vep_amount = fields.Monetary(
        string="VEP Amount",
        currency_field='currency_ars_id',
        readonly=True,
        group_operator=None,
        help="VEP amount of the parent operation, repeated on every line of that "
             "operation. Not aggregated, since summing it would multiply it by the "
             "number of lines. Use VEP Amount (Prorated) to add up amounts.",
    )
    vep_amount_share = fields.Monetary(
        string="VEP Amount (Prorated)",
        currency_field='currency_ars_id',
        readonly=True,
        help="Share of the operation VEP allocated to this line, in ARS.\n"
             "Formula: operation VEP amount x line share.\n"
             "Summing it over a whole operation gives back the operation VEP amount.",
    )
    amount_fob = fields.Monetary(
        string="FOB Amount",
        currency_field='currency_id',
        readonly=True,
        group_operator=None,
        help="FOB amount of the parent operation, repeated on every line of that "
             "operation. Not aggregated, since summing it would multiply it by the "
             "number of lines. Use FOB Prorated (Company Currency) to add up amounts.",
    )
    amount_fob_usd = fields.Monetary(
        string="FOB Amount (USD)",
        currency_field='currency_usd_id',
        readonly=True,
        group_operator=None,
        help="FOB amount of the parent operation expressed in USD, repeated on every "
             "line of that operation. Not aggregated, since summing it would multiply "
             "it by the number of lines.",
    )
    amount_cif = fields.Monetary(
        string="CIF Amount",
        currency_field='currency_id',
        readonly=True,
        group_operator=None,
        help="CIF amount of the parent operation, repeated on every line of that "
             "operation. Not aggregated, since summing it would multiply it by the "
             "number of lines. Use CIF Prorated (Company Currency) to add up amounts.",
    )
    amount_fob_share_company = fields.Monetary(
        string="FOB Prorated (Company Currency)",
        currency_field='company_currency_id',
        readonly=True,
        help="Share of the operation FOB amount allocated to this line.\n"
             "Formula: (operation FOB amount x line share) / operation currency rate.\n"
             "Summing it over a whole operation gives back the operation FOB amount "
             "converted to the company currency.",
    )
    amount_cif_share_company = fields.Monetary(
        string="CIF Prorated (Company Currency)",
        currency_field='company_currency_id',
        readonly=True,
        help="Share of the operation CIF amount allocated to this line.\n"
             "Formula: (operation CIF amount x line share) / operation currency rate.\n"
             "Summing it over a whole operation gives back the operation CIF amount "
             "converted to the company currency.",
    )

    # -------------------------------------------------------------------------
    # ACTION METHODS
    # -------------------------------------------------------------------------
    def action_open_operation(self):
        """Open the parent COMEX operation of this line."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _("COMEX Operation"),
            'res_model': 'comex.operation',
            'res_id': self.operation_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # -------------------------------------------------------------------------
    # SQL VIEW
    # -------------------------------------------------------------------------
    @property
    def _table_query(self):
        return '%s %s %s' % (
            self._with(),
            self._select_product_lines(),
            self._select_operations_without_lines(),
        )

    @api.model
    def _with(self):
        """Per-operation aggregates used to prorate the header amounts."""
        return """
            WITH operation_totals AS (
                SELECT
                    line.operation_id AS operation_id,
                    COUNT(*) AS line_count,
                    SUM(line.price_subtotal) AS lines_total
                FROM comex_operation_product_line line
                GROUP BY line.operation_id
            )
        """

    @api.model
    def _select_product_lines(self):
        """One row per COMEX product line."""
        share = self._share_expression()
        return """
            SELECT
                line.id * 2 AS id,
                line.id AS product_line_id,
                TRUE AS has_product_line,
                line.sequence AS sequence,
                line.operation_id AS operation_id,
                operation.active AS active,
                operation.name AS operation_name,
                operation.operation_type AS operation_type,
                operation.stage_id AS stage_id,
                operation.color AS color,
                operation.partner_id AS partner_id,
                operation.date_operation AS date_operation,
                operation.date_etd AS date_etd,
                operation.date_eta AS date_eta,
                operation.date_arrival AS date_arrival,
                operation.transport_mode AS transport_mode,
                operation.origin_country_id AS origin_country_id,
                operation.container_total_count AS container_total_count,
                {bl_numbers} AS bl_numbers,
                operation.payment_terms_display AS payment_terms_display,
                operation.nominated_bank_id AS nominated_bank_id,
                operation.commercial_payment_status AS commercial_payment_status,
                operation.customs_payment_status AS customs_payment_status,
                operation.purchase_order_payment_status AS purchase_order_payment_status,
                operation.sale_order_payment_status AS sale_order_payment_status,
                operation.company_id AS company_id,
                operation.currency_mismatch AS currency_mismatch,
                operation.currency_id AS currency_id,
                operation.currency_ars_id AS currency_ars_id,
                operation.currency_usd_id AS currency_usd_id,
                company.currency_id AS company_currency_id,
                line.product_id AS product_id,
                line.product_tmpl_id AS product_tmpl_id,
                line.product_uom AS product_uom_id,
                line.product_qty AS product_qty,
                line.qty_received AS qty_received,
                line.qty_delivered AS qty_delivered,
                line.price_unit AS price_unit,
                line.price_unit_usd AS price_unit_usd,
                {price_unit_company} AS price_unit_company,
                line.price_subtotal AS price_subtotal,
                line.origin_currency_id AS origin_currency_id,
                line.price_subtotal_usd AS price_subtotal_usd,
                {price_subtotal_company} AS price_subtotal_company,
                line.origin_type AS origin_type,
                line.purchase_order_id AS purchase_order_id,
                line.sale_order_id AS sale_order_id,
                line.current_location_display AS current_location_display,
                line.lot_name_display AS lot_name_display,
                line.last_delivery_partner_id AS last_delivery_partner_id,
                {share} AS line_share,
                operation.vep_amount AS vep_amount,
                operation.vep_amount * {share} AS vep_amount_share,
                operation.amount_fob AS amount_fob,
                operation.amount_fob_usd AS amount_fob_usd,
                operation.amount_cif AS amount_cif,
                {amount_fob_share_company} AS amount_fob_share_company,
                {amount_cif_share_company} AS amount_cif_share_company
            FROM comex_operation_product_line line
            JOIN comex_operation operation ON operation.id = line.operation_id
            JOIN operation_totals totals ON totals.operation_id = line.operation_id
            JOIN res_company company ON company.id = operation.company_id
        """.format(
            bl_numbers=self._bl_numbers_expression(),
            share=share,
            price_unit_company=self._to_company_currency('line.price_unit'),
            price_subtotal_company=self._to_company_currency('line.price_subtotal'),
            amount_fob_share_company=self._to_company_currency('operation.amount_fob * %s' % share),
            amount_cif_share_company=self._to_company_currency('operation.amount_cif * %s' % share),
        )

    @api.model
    def _select_operations_without_lines(self):
        """One synthetic row per operation that has no product line at all."""
        return """
            UNION ALL
            SELECT
                operation.id * 2 + 1 AS id,
                NULL::integer AS product_line_id,
                FALSE AS has_product_line,
                0 AS sequence,
                operation.id AS operation_id,
                operation.active AS active,
                operation.name AS operation_name,
                operation.operation_type AS operation_type,
                operation.stage_id AS stage_id,
                operation.color AS color,
                operation.partner_id AS partner_id,
                operation.date_operation AS date_operation,
                operation.date_etd AS date_etd,
                operation.date_eta AS date_eta,
                operation.date_arrival AS date_arrival,
                operation.transport_mode AS transport_mode,
                operation.origin_country_id AS origin_country_id,
                operation.container_total_count AS container_total_count,
                {bl_numbers} AS bl_numbers,
                operation.payment_terms_display AS payment_terms_display,
                operation.nominated_bank_id AS nominated_bank_id,
                operation.commercial_payment_status AS commercial_payment_status,
                operation.customs_payment_status AS customs_payment_status,
                operation.purchase_order_payment_status AS purchase_order_payment_status,
                operation.sale_order_payment_status AS sale_order_payment_status,
                operation.company_id AS company_id,
                operation.currency_mismatch AS currency_mismatch,
                operation.currency_id AS currency_id,
                operation.currency_ars_id AS currency_ars_id,
                operation.currency_usd_id AS currency_usd_id,
                company.currency_id AS company_currency_id,
                NULL::integer AS product_id,
                NULL::integer AS product_tmpl_id,
                NULL::integer AS product_uom_id,
                0.0::numeric AS product_qty,
                0.0::numeric AS qty_received,
                0.0::numeric AS qty_delivered,
                0.0::numeric AS price_unit,
                0.0::numeric AS price_unit_usd,
                0.0::numeric AS price_unit_company,
                0.0::numeric AS price_subtotal,
                operation.currency_id AS origin_currency_id,
                0.0::numeric AS price_subtotal_usd,
                0.0::numeric AS price_subtotal_company,
                NULL::varchar AS origin_type,
                NULL::integer AS purchase_order_id,
                NULL::integer AS sale_order_id,
                NULL::varchar AS current_location_display,
                NULL::varchar AS lot_name_display,
                NULL::integer AS last_delivery_partner_id,
                1.0::numeric AS line_share,
                operation.vep_amount AS vep_amount,
                operation.vep_amount AS vep_amount_share,
                operation.amount_fob AS amount_fob,
                operation.amount_fob_usd AS amount_fob_usd,
                operation.amount_cif AS amount_cif,
                {amount_fob_share_company} AS amount_fob_share_company,
                {amount_cif_share_company} AS amount_cif_share_company
            FROM comex_operation operation
            JOIN res_company company ON company.id = operation.company_id
            WHERE NOT EXISTS (
                SELECT 1
                FROM comex_operation_product_line line
                WHERE line.operation_id = operation.id
            )
        """.format(
            bl_numbers=self._bl_numbers_expression(),
            amount_fob_share_company=self._to_company_currency('operation.amount_fob'),
            amount_cif_share_company=self._to_company_currency('operation.amount_cif'),
        )

    @api.model
    def _share_expression(self):
        """Weight of a line within its operation, with an equal-split fallback."""
        return """(CASE
                    WHEN totals.lines_total > 0 THEN line.price_subtotal / totals.lines_total
                    ELSE 1.0 / totals.line_count
                END)"""

    @api.model
    def _bl_numbers_expression(self):
        """Comma-separated BL numbers of the active shipments of the operation."""
        return """(
                    SELECT string_agg(shipment.name, ', ' ORDER BY shipment.name)
                    FROM comex_shipment shipment
                    WHERE shipment.operation_id = operation.id AND shipment.active
                )"""

    @api.model
    def _to_company_currency(self, amount):
        """Convert an amount from the operation currency to the company currency."""
        return '((%s) / COALESCE(NULLIF(operation.currency_rate, 0), 1.0))' % amount
