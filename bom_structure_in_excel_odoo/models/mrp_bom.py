import io
import json
import xlsxwriter
from odoo import models
from odoo.tools import date_utils


class AccountMove(models.Model):
    _inherit = 'mrp.bom'

    def action_print_bom_structure(self):
        bom = self.env['mrp.bom'].browse(self.id)
        candidates = bom.product_id or bom.product_tmpl_id.product_variant_ids
        quantity = bom.product_qty
        for product_variant_id in candidates.ids:
            doc = self.env['report.mrp.report_bom_structure']._get_pdf_line(
                bom.id, product_id=product_variant_id,
                qty=quantity, unfolded=True)
        return {
            'type': 'ir.actions.report',
            'data': {'model': 'mrp.bom',
                     'options': json.dumps(doc,
                                           default=date_utils.json_default),
                     'output_format': 'xlsx',
                     'report_name': 'BoM Structure',
                     },
            'report_type': 'xlsx',
        }

    def get_xlsx_report(self, data, response):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet()

        # Formats
        header_format = workbook.add_format({'align': 'left', 'bold': True, 'font_size': 14})
        subheader_format = workbook.add_format({'font_size': 12, 'bold': True})
        cell_format = workbook.add_format({'font_size': 10})
        bold_format = workbook.add_format({'font_size': 10, 'bold': True})
        green_format = workbook.add_format({'font_size': 10, 'font_color': 'green'})
        red_format = workbook.add_format({'font_size': 10, 'font_color': 'red'})

        # Title
        sheet.write('A1', 'BoM Structure & Cost', header_format)
        sheet.write('A3', data['name'], subheader_format)

        # Headers
        headers = [
            'Index', 'Products', 'Quantity', 'Unit of Measure', 'Ready to Produce',
            'Free to Use', 'On Hand', 'Availability', 'Lead Time', 'Route',
            'Product Cost', 'BOM Cost'
        ]
        for col_num, header in enumerate(headers):
            sheet.write(5, col_num, header, bold_format)

        # Write rows
        row = 6  # Start writing data from row 7
        currency_symbol = self.env.user.company_id.currency_id.symbol

        # Variables para seguimiento de índices
        current_level_indices = {0: 1}  # Índice para el nivel 0 (raíz)

        for line in data.get('lines', []):
            # Indentation for nested levels
            level = line.get('level', 0)
            indent = ' ' * (level * 4)

            # Generar índice jerárquico
            if level == 0:
                index = current_level_indices[0]
                current_level_indices[0] += 1
                current_level_indices[1] = 1  # Reiniciar índice de hijos
            else:
                parent_index = current_level_indices.get(level - 1, 1)
                index = f"{parent_index}.{current_level_indices.get(level, 1)}"

                # Incrementar índice de hermanos en este nivel
                current_level_indices[level] = current_level_indices.get(level, 1) + 1

            # Write data
            sheet.write(row, 0, index, cell_format)  # Index
            sheet.write(row, 1, f"{indent}{line.get('name', '')}", cell_format)  # Product name
            sheet.write(row, 2, line.get('quantity', ''), cell_format)  # Quantity
            sheet.write(row, 3, line.get('uom', ''), cell_format)  # Unit of Measure
            sheet.write(row, 4, line.get('producible_qty', ''), cell_format)  # Ready to Produce
            sheet.write(row, 5, line.get('quantity_available', ''), cell_format)  # Free to Use
            sheet.write(row, 6, line.get('quantity_on_hand', ''), cell_format)  # On Hand

            # Availability color coding
            availability = line.get('availability_display', '')
            availability_format = (
                green_format if availability == 'Available' else red_format
            )
            sheet.write(row, 7, availability, availability_format)

            # Lead Time
            lead_time = f"{int(line.get('lead_time', 0))} days"
            sheet.write(row, 8, lead_time, cell_format)

            # Route
            route = f"{line.get('route_name', '')} {line.get('route_detail', '')}".strip()
            sheet.write(row, 9, route, cell_format)

            # Costs
            product_cost = line.get('prod_cost', 0)
            bom_cost = line.get('bom_cost', 0)
            sheet.write(row, 10, f"{currency_symbol} {product_cost:.2f}", cell_format)
            sheet.write(row, 11, f"{currency_symbol} {bom_cost:.2f}", cell_format)

            row += 1

        # Finalize workbook
        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()