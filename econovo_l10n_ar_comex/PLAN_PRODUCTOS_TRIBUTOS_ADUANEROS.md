# Plan de Implementación: Sistema Configurable de Productos y Tributos Aduaneros

## 📋 Objetivo

Implementar un sistema **100% configurable desde UI** para parsear automáticamente facturas tipo 66 (Despacho de Importación) hacia `comex.customs.clearance`, **sin hardcodear ningún mapeo** en código Python.

---

## 🎯 Principios de Diseño

1. ❌ **CERO hardcoding** - Ni códigos internos, ni keywords, ni mappings
2. ✅ **100% configurable** - Todo desde interfaz Odoo
3. ✅ **Flexible** - Soporta cualquier esquema de productos/conceptos
4. ✅ **Extensible** - Fácil agregar nuevos tributos
5. ✅ **Auditable** - Trazabilidad de qué se parseó y cómo

---

## 🏗️ Arquitectura Propuesta

### **Modelo 1: `comex.tribute.product.mapping`**
**Propósito:** Mapear productos específicos a campos de `customs_clearance`

```python
class ComexTributeProductMapping(models.Model):
    _name = 'comex.tribute.product.mapping'
    _description = 'COMEX Tribute Product Mapping'
    _order = 'sequence, id'
    
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    
    # Producto a reconocer
    product_id = fields.Many2one(
        'product.product',
        string="Product",
        required=True,
        domain="[('detailed_type', '=', 'service')]",
        help="Product to identify in Type 66 invoice lines"
    )
    
    # Campo destino en customs_clearance
    tribute_field = fields.Selection(
        selection=[
            ('amount_duties', 'Import Duties (DIE)'),
            ('amount_statistics', 'Statistics Fee'),
            ('amount_vat', 'VAT'),
            ('amount_vat_additional', 'Additional VAT'),
            ('amount_income_tax', 'Income Tax Perception'),
            ('amount_gross_income', 'Gross Income Perception'),
            ('amount_taxes', 'Other Taxes'),
            ('amount_fees', 'Other Fees'),
        ],
        string="Tribute Field",
        required=True,
        help="Target field in Customs Clearance where amount will be accumulated"
    )
    
    # Metadatos
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    notes = fields.Text(string="Internal Notes")
```

**Vista Tree/Form para configuración fácil en:**
`Settings > COMEX > Tribute Product Mappings`

---

### **Modelo 2: `comex.tribute.keyword.mapping`**
**Propósito:** Mapear keywords/patrones textuales a campos (fallback sin productos)

```python
class ComexTributeKeywordMapping(models.Model):
    _name = 'comex.tribute.keyword.mapping'
    _description = 'COMEX Tribute Keyword Mapping'
    _order = 'sequence, id'
    
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    
    # Patrón de texto a buscar
    name = fields.Char(
        string="Keyword/Pattern",
        required=True,
        help="Text to search in invoice line description (case-insensitive). Examples: 'DIE', 'Derecho de Importación', 'Tasa Estadística'"
    )
    
    # Tipo de búsqueda
    match_type = fields.Selection(
        selection=[
            ('contains', 'Contains (anywhere in text)'),
            ('exact', 'Exact Match'),
            ('starts_with', 'Starts With'),
            ('ends_with', 'Ends With'),
            ('regex', 'Regular Expression'),
        ],
        string="Match Type",
        default='contains',
        required=True,
    )
    
    # Campo destino
    tribute_field = fields.Selection(
        selection=[
            ('amount_duties', 'Import Duties (DIE)'),
            ('amount_statistics', 'Statistics Fee'),
            ('amount_vat', 'VAT'),
            ('amount_vat_additional', 'Additional VAT'),
            ('amount_income_tax', 'Income Tax Perception'),
            ('amount_gross_income', 'Gross Income Perception'),
            ('amount_taxes', 'Other Taxes'),
            ('amount_fees', 'Other Fees'),
        ],
        string="Tribute Field",
        required=True,
    )
    
    # Opciones avanzadas
    priority = fields.Integer(
        default=10,
        help="Higher priority = checked first. Use when multiple patterns might match."
    )
    stop_on_match = fields.Boolean(
        default=True,
        help="If checked, stops searching after first match (prevents double counting)"
    )
    
    # Metadatos
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    notes = fields.Text(string="Internal Notes / Examples")
```

**Vista Tree/Form para configuración en:**
`Settings > COMEX > Tribute Keyword Mappings`

---

### **Modelo 3: `comex.tribute.parse.log`** (Opcional - Auditoría)
**Propósito:** Registrar qué se parseó y cómo para debugging

```python
class ComexTributeParseLog(models.Model):
    _name = 'comex.tribute.parse.log'
    _description = 'COMEX Tribute Parsing Log'
    _order = 'create_date desc'
    
    customs_clearance_id = fields.Many2one('comex.customs.clearance', required=True, ondelete='cascade')
    invoice_id = fields.Many2one('account.move', required=True)
    invoice_line_id = fields.Many2one('account.move.line', required=True)
    
    matched_by = fields.Selection([
        ('product', 'Product Mapping'),
        ('keyword', 'Keyword Mapping'),
        ('manual', 'Manual Override'),
        ('unmatched', 'Unmatched'),
    ], required=True)
    
    mapping_record = fields.Char(
        help="Reference to mapping record used (e.g., 'comex.tribute.product.mapping,5')"
    )
    
    tribute_field = fields.Char(help="Target field name (e.g., 'amount_duties')")
    amount_parsed = fields.Monetary(currency_field='currency_id')
    currency_id = fields.Many2one('res.currency')
    
    line_description = fields.Text(help="Invoice line description at parse time")
    product_name = fields.Char(help="Product name at parse time")
```

---

## 🔧 Lógica de Parsing (Sin Hardcoding)

### **Método mejorado en `comex_customs_clearance.py`:**

```python
def _parse_tribute_lines_from_invoice(self, invoice):
    """Parse invoice lines using configured mappings (zero hardcoding).
    
    Parsing order:
    1. Product-based mapping (exact match by product_id)
    2. Keyword-based mapping (text pattern matching)
    3. Log unmatched lines for manual review
    """
    if not invoice or not invoice.invoice_line_ids:
        return
    
    # Reset amounts
    tribute_fields = [
        'amount_duties', 'amount_statistics', 'amount_vat', 'amount_vat_additional',
        'amount_income_tax', 'amount_gross_income', 'amount_taxes', 'amount_fees'
    ]
    for field in tribute_fields:
        setattr(self, field, 0)
    
    # Get active mappings
    ProductMapping = self.env['comex.tribute.product.mapping'].sudo()
    KeywordMapping = self.env['comex.tribute.keyword.mapping'].sudo()
    ParseLog = self.env['comex.tribute.parse.log'].sudo()
    
    product_mappings = ProductMapping.search([
        ('active', '=', True),
        '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)
    ])
    
    keyword_mappings = KeywordMapping.search([
        ('active', '=', True),
        '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)
    ], order='priority desc, sequence')
    
    # Build product→field lookup (fast)
    product_to_field = {m.product_id.id: m.tribute_field for m in product_mappings}
    
    for line in invoice.invoice_line_ids:
        amount = abs(line.price_subtotal)
        matched = False
        match_info = {}
        
        # STEP 1: Try product mapping (exact match)
        if line.product_id and line.product_id.id in product_to_field:
            field_name = product_to_field[line.product_id.id]
            current_value = getattr(self, field_name, 0)
            setattr(self, field_name, current_value + amount)
            matched = True
            match_info = {
                'matched_by': 'product',
                'mapping_record': f'comex.tribute.product.mapping,{product_mappings.filtered(lambda m: m.product_id.id == line.product_id.id).id}',
                'tribute_field': field_name,
            }
        
        # STEP 2: Try keyword mapping (if no product match)
        if not matched:
            line_text = (line.name or '') + ' ' + (line.product_id.name or '')
            line_text = line_text.lower().strip()
            
            for mapping in keyword_mappings:
                is_match = self._check_keyword_match(line_text, mapping)
                
                if is_match:
                    field_name = mapping.tribute_field
                    current_value = getattr(self, field_name, 0)
                    setattr(self, field_name, current_value + amount)
                    matched = True
                    match_info = {
                        'matched_by': 'keyword',
                        'mapping_record': f'comex.tribute.keyword.mapping,{mapping.id}',
                        'tribute_field': field_name,
                    }
                    if mapping.stop_on_match:
                        break
        
        # STEP 3: Log result (for audit/debugging)
        if matched:
            ParseLog.create({
                'customs_clearance_id': self.id,
                'invoice_id': invoice.id,
                'invoice_line_id': line.id,
                'matched_by': match_info['matched_by'],
                'mapping_record': match_info['mapping_record'],
                'tribute_field': match_info['tribute_field'],
                'amount_parsed': amount,
                'currency_id': invoice.currency_id.id,
                'line_description': line.name,
                'product_name': line.product_id.name if line.product_id else False,
            })
        else:
            # Log unmatched for manual review
            ParseLog.create({
                'customs_clearance_id': self.id,
                'invoice_id': invoice.id,
                'invoice_line_id': line.id,
                'matched_by': 'unmatched',
                'amount_parsed': amount,
                'currency_id': invoice.currency_id.id,
                'line_description': line.name,
                'product_name': line.product_id.name if line.product_id else False,
            })

def _check_keyword_match(self, text, mapping):
    """Check if text matches keyword mapping based on match_type."""
    import re
    
    keyword = mapping.name.lower()
    match_type = mapping.match_type
    
    if match_type == 'contains':
        return keyword in text
    elif match_type == 'exact':
        return text == keyword
    elif match_type == 'starts_with':
        return text.startswith(keyword)
    elif match_type == 'ends_with':
        return text.endswith(keyword)
    elif match_type == 'regex':
        try:
            return bool(re.search(keyword, text, re.IGNORECASE))
        except:
            return False
    return False
```

---

## 📦 Data Demo (Instalación Inicial)

### **Archivo: `data/comex_tribute_mappings_demo.xml`**

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">

    <!-- ============================================ -->
    <!-- Products for Customs Tributes               -->
    <!-- ============================================ -->
    
    <record id="product_comex_die" model="product.product">
        <field name="name">DIE - Derecho de Importación Extrazona</field>
        <field name="detailed_type">service</field>
        <field name="default_code">AFIP_DESPACHO</field>
        <field name="sale_ok" eval="False"/>
        <field name="purchase_ok" eval="True"/>
        <field name="categ_id" ref="product.product_category_all"/>
        <field name="supplier_taxes_id" eval="False"/>
    </record>
    
    <record id="product_comex_statistics" model="product.product">
        <field name="name">Tasa de Estadística</field>
        <field name="detailed_type">service</field>
        <field name="default_code">AFIP_TASA_EST</field>
        <field name="sale_ok" eval="False"/>
        <field name="purchase_ok" eval="True"/>
        <field name="supplier_taxes_id" eval="False"/>
    </record>
    
    <record id="product_comex_tariff" model="product.product">
        <field name="name">Arancel</field>
        <field name="detailed_type">service</field>
        <field name="default_code">AFIP_ARANCEL</field>
        <field name="sale_ok" eval="False"/>
        <field name="purchase_ok" eval="True"/>
        <field name="supplier_taxes_id" eval="False"/>
    </record>
    
    <record id="product_comex_guard_service" model="product.product">
        <field name="name">Servicio de Guarda</field>
        <field name="detailed_type">service</field>
        <field name="default_code">AFIP_SERV_GUARDA</field>
        <field name="sale_ok" eval="False"/>
        <field name="purchase_ok" eval="True"/>
        <field name="supplier_taxes_id" eval="False"/>
    </record>
    
    <record id="product_comex_vat" model="product.product">
        <field name="name">IVA Importación</field>
        <field name="detailed_type">service</field>
        <field name="default_code">AFIP_IVA_IMP</field>
        <field name="sale_ok" eval="False"/>
        <field name="purchase_ok" eval="True"/>
        <field name="supplier_taxes_id" eval="False"/>
    </record>
    
    <record id="product_comex_perc_iigg" model="product.product">
        <field name="name">Percepción IIGG</field>
        <field name="detailed_type">service</field>
        <field name="default_code">AFIP_PERC_IIGG</field>
        <field name="sale_ok" eval="False"/>
        <field name="purchase_ok" eval="True"/>
        <field name="supplier_taxes_id" eval="False"/>
    </record>
    
    <record id="product_comex_perc_iibb" model="product.product">
        <field name="name">Percepción IIBB</field>
        <field name="detailed_type">service</field>
        <field name="default_code">AFIP_PERC_IIBB</field>
        <field name="sale_ok" eval="False"/>
        <field name="purchase_ok" eval="True"/>
        <field name="supplier_taxes_id" eval="False"/>
    </record>

    <!-- ============================================ -->
    <!-- Product Mappings (Configurable)             -->
    <!-- ============================================ -->
    
    <record id="mapping_product_die" model="comex.tribute.product.mapping">
        <field name="sequence">10</field>
        <field name="product_id" ref="product_comex_die"/>
        <field name="tribute_field">amount_duties</field>
        <field name="notes">Default mapping for Import Duties (DIE)</field>
    </record>
    
    <record id="mapping_product_statistics" model="comex.tribute.product.mapping">
        <field name="sequence">20</field>
        <field name="product_id" ref="product_comex_statistics"/>
        <field name="tribute_field">amount_statistics</field>
        <field name="notes">Default mapping for Statistics Fee (3% of CIF)</field>
    </record>
    
    <record id="mapping_product_tariff" model="comex.tribute.product.mapping">
        <field name="sequence">30</field>
        <field name="product_id" ref="product_comex_tariff"/>
        <field name="tribute_field">amount_duties</field>
        <field name="notes">Alternative mapping for Tariff (also goes to DIE)</field>
    </record>
    
    <record id="mapping_product_guard" model="comex.tribute.product.mapping">
        <field name="sequence">40</field>
        <field name="product_id" ref="product_comex_guard_service"/>
        <field name="tribute_field">amount_fees</field>
        <field name="notes">Mapping for Guard Service fees</field>
    </record>
    
    <record id="mapping_product_vat" model="comex.tribute.product.mapping">
        <field name="sequence">50</field>
        <field name="product_id" ref="product_comex_vat"/>
        <field name="tribute_field">amount_vat</field>
        <field name="notes">Mapping for Import VAT</field>
    </record>
    
    <record id="mapping_product_perc_iigg" model="comex.tribute.product.mapping">
        <field name="sequence">60</field>
        <field name="product_id" ref="product_comex_perc_iigg"/>
        <field name="tribute_field">amount_income_tax</field>
        <field name="notes">Mapping for Income Tax Perception</field>
    </record>
    
    <record id="mapping_product_perc_iibb" model="comex.tribute.product.mapping">
        <field name="sequence">70</field>
        <field name="product_id" ref="product_comex_perc_iibb"/>
        <field name="tribute_field">amount_gross_income</field>
        <field name="notes">Mapping for Gross Income Perception</field>
    </record>

    <!-- ============================================ -->
    <!-- Keyword Mappings (Fallback - Configurable)  -->
    <!-- ============================================ -->
    
    <record id="mapping_keyword_die_1" model="comex.tribute.keyword.mapping">
        <field name="sequence">10</field>
        <field name="priority">100</field>
        <field name="name">die</field>
        <field name="match_type">contains</field>
        <field name="tribute_field">amount_duties</field>
        <field name="stop_on_match" eval="True"/>
        <field name="notes">Matches: DIE, D.I.E.</field>
    </record>
    
    <record id="mapping_keyword_die_2" model="comex.tribute.keyword.mapping">
        <field name="sequence">11</field>
        <field name="priority">95</field>
        <field name="name">derecho de importación</field>
        <field name="match_type">contains</field>
        <field name="tribute_field">amount_duties</field>
        <field name="stop_on_match" eval="True"/>
        <field name="notes">Full name in Spanish</field>
    </record>
    
    <record id="mapping_keyword_statistics_1" model="comex.tribute.keyword.mapping">
        <field name="sequence">20</field>
        <field name="priority">100</field>
        <field name="name">tasa estadística</field>
        <field name="match_type">contains</field>
        <field name="tribute_field">amount_statistics</field>
        <field name="stop_on_match" eval="True"/>
        <field name="notes">Statistics Fee (3%)</field>
    </record>
    
    <record id="mapping_keyword_statistics_2" model="comex.tribute.keyword.mapping">
        <field name="sequence">21</field>
        <field name="priority">95</field>
        <field name="name">estadística</field>
        <field name="match_type">contains</field>
        <field name="tribute_field">amount_statistics</field>
        <field name="stop_on_match" eval="True"/>
    </record>
    
    <record id="mapping_keyword_vat" model="comex.tribute.keyword.mapping">
        <field name="sequence">30</field>
        <field name="priority">90</field>
        <field name="name">iva importación</field>
        <field name="match_type">contains</field>
        <field name="tribute_field">amount_vat</field>
        <field name="stop_on_match" eval="True"/>
    </record>
    
    <record id="mapping_keyword_perc_iigg_1" model="comex.tribute.keyword.mapping">
        <field name="sequence">40</field>
        <field name="priority">100</field>
        <field name="name">percepción ganancias</field>
        <field name="match_type">contains</field>
        <field name="tribute_field">amount_income_tax</field>
        <field name="stop_on_match" eval="True"/>
    </record>
    
    <record id="mapping_keyword_perc_iigg_2" model="comex.tribute.keyword.mapping">
        <field name="sequence">41</field>
        <field name="priority">95</field>
        <field name="name">perc. iigg</field>
        <field name="match_type">contains</field>
        <field name="tribute_field">amount_income_tax</field>
        <field name="stop_on_match" eval="True"/>
    </record>
    
    <record id="mapping_keyword_perc_iibb_1" model="comex.tribute.keyword.mapping">
        <field name="sequence">50</field>
        <field name="priority">100</field>
        <field name="name">percepción iibb</field>
        <field name="match_type">contains</field>
        <field name="tribute_field">amount_gross_income</field>
        <field name="stop_on_match" eval="True"/>
    </record>
    
    <record id="mapping_keyword_perc_iibb_2" model="comex.tribute.keyword.mapping">
        <field name="sequence">51</field>
        <field name="priority">95</field>
        <field name="name">ingresos brutos</field>
        <field name="match_type">contains</field>
        <field name="tribute_field">amount_gross_income</field>
        <field name="stop_on_match" eval="True"/>
    </record>
    
    <record id="mapping_keyword_guard" model="comex.tribute.keyword.mapping">
        <field name="sequence">60</field>
        <field name="priority">100</field>
        <field name="name">servicio de guarda</field>
        <field name="match_type">contains</field>
        <field name="tribute_field">amount_fees</field>
        <field name="stop_on_match" eval="True"/>
    </record>
    
    <record id="mapping_keyword_arancel" model="comex.tribute.keyword.mapping">
        <field name="sequence">70</field>
        <field name="priority">90</field>
        <field name="name">arancel</field>
        <field name="match_type">contains</field>
        <field name="tribute_field">amount_duties</field>
        <field name="stop_on_match" eval="True"/>
    </record>

</odoo>
```

---

## 🎨 Vistas de Configuración

### **Vista Menú en Settings:**

```xml
<!-- Menu item in Settings -->
<menuitem id="menu_comex_tribute_config"
          name="COMEX Tribute Mappings"
          parent="base.menu_administration"
          sequence="100"/>

<menuitem id="menu_comex_tribute_product_mapping"
          name="Product Mappings"
          parent="menu_comex_tribute_config"
          action="action_comex_tribute_product_mapping"
          sequence="10"/>

<menuitem id="menu_comex_tribute_keyword_mapping"
          name="Keyword Mappings"
          parent="menu_comex_tribute_config"
          action="action_comex_tribute_keyword_mapping"
          sequence="20"/>

<menuitem id="menu_comex_tribute_parse_log"
          name="Parsing Logs (Debug)"
          parent="menu_comex_tribute_config"
          action="action_comex_tribute_parse_log"
          sequence="30"
          groups="base.group_no_one"/>
```

---

## 🚀 Flujo de Trabajo del Usuario

### **Configuración Inicial (Una sola vez):**

1. **Crear Productos para Tributos:**
   - `Contabilidad > Configuración > Productos > Crear`
   - Nombre: "DIE - Derecho de Importación"
   - Tipo: Servicio
   - Código: AFIP_DESPACHO (opcional)
   - *(O usar los productos demo creados automáticamente)*

2. **Configurar Mapeos de Productos:**
   - `Ajustes > COMEX Tribute Mappings > Product Mappings > Crear`
   - Producto: [DIE - Derecho de Importación]
   - Campo: Import Duties (DIE)
   - *(Repetir para cada tributo)*

3. **Configurar Mapeos de Keywords (Opcional - Fallback):**
   - `Ajustes > COMEX Tribute Mappings > Keyword Mappings > Crear`
   - Keyword: "derecho de importación"
   - Tipo: Contains
   - Campo: Import Duties (DIE)

### **Uso Diario:**

1. **Registrar Factura Tipo 66:**
   - `Contabilidad > Proveedores > Facturas > Crear`
   - Proveedor: AFIP / Despachante
   - Tipo Doc: (66) IMPORT CLEARANCE
   - Número: 16052IC04000605L
   - Líneas: Usar productos configurados
     - [DIE - Derecho de Importación]: ARS 5,064.98
     - [Tasa de Estadística]: ARS 152.08
     - [Arancel]: ARS 10.00
     - [Servicio de Guarda]: ARS 28.00

2. **Crear Customs Clearance:**
   - `COMEX > Operations > [Operación] > Create Customs Clearance`
   - Seleccionar `vendor_bill_id`: [Factura tipo 66 creada]
   - **Automáticamente se llenan:**
     - ✅ `dispatch_number`: 16052IC04000605L
     - ✅ `vep_amount`: ARS 5,255.06
     - ✅ `amount_duties`: ARS 5,064.98 + 10.00 = 5,074.98
     - ✅ `amount_statistics`: ARS 152.08
     - ✅ `amount_fees`: ARS 28.00

3. **Revisar Parsing Log (Si algo falla):**
   - `Ajustes > COMEX > Parsing Logs`
   - Ver qué líneas no se parsearon
   - Ajustar mapeos según necesidad

---

## 🔍 Casos Edge Resueltos

### **1. Líneas sin Producto (Solo Descripción)**
**Problema:** Línea de factura manual sin producto, solo texto  
**Solución:** Keyword mapping hace match en `line.name`

**Ejemplo:**
```xml
<field name="invoice_line_ids">
    (0, 0, {'name': 'Derecho de Importación Extrazona', 'price_unit': 1000})
</field>
```
✅ **Match:** Keyword "derecho de importación" → `amount_duties`

---

### **2. Productos Personalizados del Cliente**
**Problema:** Cliente ya tiene productos propios con nombres distintos  
**Solución:** Crear mappings para SUS productos

**Ejemplo:**
- Cliente tiene producto: "Tributo ARCA - DIE"
- Crear mapping: Producto "Tributo ARCA - DIE" → `amount_duties`

---

### **3. Múltiples Productos para Mismo Tributo**
**Problema:** DIE y Arancel deben ir ambos a `amount_duties`  
**Solución:** Crear múltiples mappings apuntando al mismo campo

**Ejemplo:**
```xml
<record id="mapping_product_die">
    <field name="product_id" ref="product_comex_die"/>
    <field name="tribute_field">amount_duties</field>
</record>

<record id="mapping_product_tariff">
    <field name="product_id" ref="product_comex_tariff"/>
    <field name="tribute_field">amount_duties</field>  <!-- ¡Mismo campo! -->
</record>
```
✅ **Resultado:** Ambos se suman en `amount_duties`

---

### **4. Regex para Patrones Complejos**
**Problema:** Detectar "Perc. IIGG", "PERC GANANCIAS", "Percepción Impuesto Ganancias"  
**Solución:** Keyword mapping con regex

**Ejemplo:**
```xml
<record id="mapping_keyword_perc_regex">
    <field name="name">perc(epción|\.)?.*?(ganancias|iigg)</field>
    <field name="match_type">regex</field>
    <field name="tribute_field">amount_income_tax</field>
</record>
```

---

### **5. Desactivar Mappings Temporalmente**
**Problema:** Quiero probar sin cierto mapping  
**Solución:** Campo `active=False` en el mapping

**UI:** Archivar el registro desde la vista tree

---

### **6. Multi-compañía con Reglas Diferentes**
**Problema:** Compañía A usa productos distintos que Compañía B  
**Solución:** Campo `company_id` en mappings

**Ejemplo:**
```python
# Mapping solo para Compañía A
<record id="mapping_die_company_a">
    <field name="company_id" ref="base.main_company"/>
    <field name="product_id" ref="product_die_a"/>
    ...
</record>

# Mapping solo para Compañía B
<record id="mapping_die_company_b">
    <field name="company_id" ref="res_company_b"/>
    <field name="product_id" ref="product_die_b"/>
    ...
</record>
```

---

## 📊 Reportes y Análisis

### **Vista de Parsing Logs (Debugging):**

```xml
<tree string="Tribute Parsing Logs" decoration-danger="matched_by == 'unmatched'">
    <field name="create_date"/>
    <field name="customs_clearance_id"/>
    <field name="invoice_id"/>
    <field name="line_description"/>
    <field name="product_name"/>
    <field name="matched_by"/>
    <field name="tribute_field"/>
    <field name="amount_parsed"/>
    <field name="currency_id"/>
</tree>
```

**Filtros útiles:**
- ⚠️ `Unmatched Lines` - Líneas que no se parsearon
- ✅ `By Product` - Parseadas por producto
- 🔤 `By Keyword` - Parseadas por keyword

---

## ✅ Beneficios de Este Enfoque

1. **CERO Hardcoding** - Todo en la base de datos
2. **Auditable** - Logs de qué se parseó y cómo
3. **Flexible** - Soporta cualquier esquema de cliente
4. **Extensible** - Agregar nuevos tributos = agregar selection
5. **Multi-tenant** - Compatible con multi-compañía
6. **Retrocompatible** - Data demo funciona out-of-the-box
7. **Debuggeable** - Logs explican por qué algo no se parseó
8. **User-friendly** - Configuración desde UI, no código

---

## 🎯 Prioridad de Implementación

### **Fase 1: MVP (Mínimo Viable)**
1. ✅ Modelo `comex.tribute.product.mapping`
2. ✅ Parsing básico por productos
3. ✅ Vista de configuración de mappings
4. ✅ Data demo con productos y mappings

### **Fase 2: Fallback Inteligente**
5. ✅ Modelo `comex.tribute.keyword.mapping`
6. ✅ Parsing por keywords con tipos de match
7. ✅ Vista de configuración de keywords

### **Fase 3: Auditoría y Debug**
8. ✅ Modelo `comex.tribute.parse.log`
9. ✅ Vista de logs con filtros
10. ✅ Notificaciones de líneas no parseadas

### **Fase 4: Extras (Opcionales)**
11. ⚡ **Botón para crear factura desde clearance** (sin wizard, formulario nativo)
    - Configuración parametrizable:
      - Tipo documento por defecto (ej: 66)
      - Proveedor por defecto (ej: AFIP)
      - Auto pre-llenar líneas (on/off)
      - Qué tributos incluir en líneas
12. ⚡ **Reportes de tributos** por operación/período (SQL View + Pivot/Graph)

---

## 📋 Fase 4.1: Crear Factura desde Clearance (Parametrizable)

### **Configuración en `res.config.settings`**

Agregar campos configurables para controlar el comportamiento del botón "Create Tribute Invoice":

```python
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
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
```

### **Modelo de Configuración de Líneas (Tabla Relacional)**

```python
class ComexTributeInvoiceLineConfig(models.Model):
    """Configuration for tribute fields to include in invoice pre-fill."""
    
    _name = 'comex.tribute.invoice.line.config'
    _description = 'COMEX Tribute Invoice Line Configuration'
    _order = 'company_id, sequence, id'
    
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Order in which tributes will appear in invoice lines",
    )
    
    company_id = fields.Many2one(
        'res.company',
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        help="Company for which this configuration applies",
    )
    
    tribute_field_id = fields.Many2one(
        'comex.tribute.field',
        string="Tribute Field",
        required=True,
        help="Tribute field to include in invoice",
    )
    
    product_id = fields.Many2one(
        'product.product',
        string="Override Product",
        domain="[('detailed_type', '=', 'service')]",
        help="Optional: Use this specific product instead of auto-detected from mappings",
    )
    
    include_if_zero = fields.Boolean(
        string="Include if Zero",
        default=False,
        help="Include this line even if amount is zero",
    )
    
    description = fields.Text(
        string="Custom Description",
        help="Optional: Override the default line description",
    )
    
    active = fields.Boolean(
        string="Active",
        default=True,
        help="Uncheck to temporarily disable this line configuration",
    )
```

### **Modelo Auxiliar para Selección de Tributos**

```python
class ComexTributeField(models.Model):
    """Master data for tribute field selection in configurations."""
    
    _name = 'comex.tribute.field'
    _description = 'COMEX Tribute Field Definition'
    _order = 'sequence, name'
    
    sequence = fields.Integer(default=10)
    
    technical_name = fields.Selection(
        selection=[
            ('amount_duties', 'Import Duties (DIE)'),
            ('amount_statistics', 'Statistics Fee'),
            ('amount_vat', 'VAT'),
            ('amount_vat_additional', 'Additional VAT'),
            ('amount_income_tax', 'Income Tax Perception'),
            ('amount_gross_income', 'Gross Income Perception'),
            ('amount_taxes', 'Other Taxes'),
            ('amount_fees', 'Other Fees'),
        ],
        string="Field Name",
        required=True,
    )
    
    name = fields.Char(
        string="Display Name",
        compute='_compute_name',
        store=True,
    )
    
    @api.depends('technical_name')
    def _compute_name(self):
        """Get display name from selection."""
        selection_dict = dict(self._fields['technical_name'].selection)
        for record in self:
            record.name = selection_dict.get(record.technical_name, record.technical_name)
```

### **Data para Tributos Configurables**

```xml
<!-- data/comex_tribute_fields_data.xml -->
<?xml version="1.0" encoding="utf-8"?>
<odoo noupdate="1">
    
    <record id="tribute_field_duties" model="comex.tribute.field">
        <field name="sequence">10</field>
        <field name="technical_name">amount_duties</field>
    </record>
    
    <record id="tribute_field_statistics" model="comex.tribute.field">
        <field name="sequence">20</field>
        <field name="technical_name">amount_statistics</field>
    </record>
    
    <record id="tribute_field_vat" model="comex.tribute.field">
        <field name="sequence">30</field>
        <field name="technical_name">amount_vat</field>
    </record>
    
    <record id="tribute_field_vat_additional" model="comex.tribute.field">
        <field name="sequence">40</field>
        <field name="technical_name">amount_vat_additional</field>
    </record>
    
    <record id="tribute_field_income_tax" model="comex.tribute.field">
        <field name="sequence">50</field>
        <field name="technical_name">amount_income_tax</field>
    </record>
    
    <record id="tribute_field_gross_income" model="comex.tribute.field">
        <field name="sequence">60</field>
        <field name="technical_name">amount_gross_income</field>
    </record>
    
    <record id="tribute_field_taxes" model="comex.tribute.field">
        <field name="sequence">70</field>
        <field name="technical_name">amount_taxes</field>
    </record>
    
    <record id="tribute_field_fees" model="comex.tribute.field">
        <field name="sequence">80</field>
        <field name="technical_name">amount_fees</field>
    </record>
    
                                               nolabel="1"
                                               context="{'default_company_id': company_id}">
                                            <tree editable="bottom">
                                                <field name="company_id" column_invisible="1"/>
                                                <field name="sequence" widget="handle"/>
                                                <field name="tribute_field_id" 
                                                       options="{'no_create': True, 'no_open': True}"/>
                                                <field name="product_id" 
                                                       optional="show"
                                                       options="{'no_create': True}"/>
                                                <field name="include_if_zero"/>
                                                <field name="description" optional="hide"/>
                                                <field name="active" widget="boolean_toggl
        <field name="name">res.config.settings.view.form.inherit.comex</field>
        <field name="model">res.config.settings</field>
        <field name="inherit_id" ref="base.res_config_settings_view_form"/>
        <field name="arch" type="xml">
            <xpath expr="//div[hasclass('settings')]" position="inside">
                <div class="app_settings_block" data-string="COMEX" string="COMEX" data-key="econovo_l10n_ar_comex">
                    <h2>Tribute Invoice Settings</h2>
                    
                    <div class="row mt16 o_settings_container">
                        <div class="col-12 col-lg-6 o_setting_box">
                            <div class="o_setting_left_pane">
                                <field name="comex_auto_prefill_invoice"/>
                            </div>
                            <div class="o_setting_right_pane">
                                <label for="comex_auto_prefill_invoice"/>
                                <div class="text-muted">
                                    Automatically pre-fill invoice lines when creating tribute invoice from customs clearance
                                </div>
                                
                                <div class="content-group" invisible="not comex_auto_prefill_invoice">
                                    <div class="mt16">
                                        <label for="comex_tribute_line_filter" class="o_light_label"/>
                                        <field name="comex_tribute_line_filter" class="oe_inline"/>
                                    </div>
                                    <div class="mt16" invisible="comex_tribute_line_filter != 'selected'">
                                        <label for="comex_tribute_line_config_ids" string="Configure Tributes to Include"/>
                                        <field name="comex_tribute_line_config_ids" nolabel="1">
                                            <tree editable="bottom">
                                                <field name="sequence" widget="handle"/>
                                                <field name="tribute_field_id" 
                                                       options="{'no_create': True, 'no_open': True}"/>
                                                <field name="product_id" 
                                                       optional="show"
                                                       options="{'no_create': True}"/>
                                                <field name="include_if_zero"/>
                                                <field name="description" optional="hide"/>
                                            </tree>
                                        </field>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <div class="col-12 col-lg-6 o_setting_box">
                            <div class="o_setting_left_pane"/>
                            <div class="o_setting_right_pane">
                                <label for="comex_default_tribute_vendor_id"/>
                                <div class="text-muted">
                                    Default vendor for tribute invoices (e.g., AFIP, Customs Broker)
                                </div>
                                <field name="comex_default_tribute_vendor_id" 
                                       placeholder="Select default vendor..."
                                       options="{'no_create': True}"/>
                            </div>
                        </div>
                        
                        <div class="col-12 col-lg-6 o_setting_box">
                            <div class="o_setting_left_pane"/>
                            <div class="o_setting_right_pane">
                                <label for="comex_default_tribute_doc_type_id"/>
                                <div class="text-muted">
                                    Default document type for tribute invoices (e.g., Type 66)
                                </div>
                                <field name="comex_default_tribute_doc_type_id" 
                                       placeholder="Select default document type..."
                                       options="{'no_create': True}"/>
                            </div>
                        </div>
                    </div>
                </div>
            </xpath>
        </field>
    </record>
</odoo>
```

### **Método Actualizado en `comex_customs_clearance.py`**

```python
def action_create_tribute_invoice(self):
    """Open native invoice form with configurable pre-filled values.
    
    Configuration via Settings > COMEX:
    - Auto pre-fill lines (on/off)
    - Which tributes to include
    - Default vendor
    - Default document type
    """
    self.ensure_one()
    
    ICP = self.env['ir.config_parameter'].sudo()
    
    # Get configuration
    auto_prefill = ICP.get_param('econovo_l10n_ar_comex.auto_prefill_invoice', default=False)
    default_vendor_id = int(ICP.get_param('econovo_l10n_ar_comex.default_tribute_vendor_id', default=0))
    default_doc_type_id = int(ICP.get_param('econovo_l10n_ar_comex.default_tribute_doc_type_id', default=0))
    
    # Build context with defaults
    context = {
        'default_move_type': 'in_invoice',
        'default_invoice_date': fields.Date.context_today(self),
        'default_ref': self.dispatch_number or f"Despacho {self.name}",
    }
    
    # Add vendor if configured
    if default_vendor_id:
        context['default_partner_id'] = default_vendor_id
    
    # Add document type if configured
    if default_doc_type_id:
        context['default_l10n_latam_document_type_id'] = default_doc_type_id
    
    # Pre-fill invoice lines if enabled
    if auto_prefill:
        invoice_lines = self._prepare_tribute_invoice_lines()
        if invoice_lines:
            context['default_invoice_line_ids'] = invoice_lines
    
    return {
        'name': _('Create Tribute Invoice'),
        'type': 'ir.actions.act_window',
        'res_model': 'account.move',
        'view_mode': 'form',
        'view_id': self.env.ref('account.view_move_form').id,
        'target': 'current',
        'context': context,
    }

def _prepare_tribute_invoice_lines(self):
    """Prepare invoice lines based on configuration."""
    ICP = self.env['ir.config_parameter'].sudo()
    line_filter = ICP.get_param('econovo_l10n_ar_comex.tribute_line_filter', default='all')
    
    # Get product mappings for fallback labels
    ProductMapping = self.env['comex.tribute.product.mapping'].sudo()
    mappings = ProductMapping.search([
        ('active', '=', True),
        '|', ('company_id', '=', False), ('company_id', '=', self.company_id.id)
    ])
    
    field_to_product = {}
    for mapping in mappings:
        if mapping.tribute_field not in field_to_product:
            field_to_product[mapping.tribute_field] = mapping.product_id
    
    tribute_field_labels = {
        'amount_duties': 'Import Duties (DIE)',
        'amount_statistics': 'Statistics Fee',
        'amount_vat': 'VAT',
        'amount_vat_additional': 'Additional VAT',
        'amount_income_tax': 'Income Tax Perception',
        'amount_gross_income': 'Gross Income Perception',
        'amount_taxes': 'Other Taxes',
        'amount_fees': 'Other Fees',
    }
    
    lines = []
    
    # Build lines based on filter mode
    if line_ficompany_id', '=', self.company_id.id),
            ('active', '=', True
        # Use configured tribute lines (ordered by sequence)
        LineConfig = self.env['comex.tribute.invoice.line.config'].sudo()
        configured_lines = LineConfig.search([
            ('res_config_id.company_id', '=', self.company_id.id)
        ], order='sequence, id')
        
        if not configured_lines:
            # No configuration found, return empty
            return lines
        
        for config_line in configured_lines:
            field_name = config_line.tribute_field_id.technical_name
            amount = getattr(self, field_name, 0)
            
            # Skip if zero and not configured to include
            if amount == 0 and not config_line.include_if_zero:
                continue
            
            # Use override product if specified, otherwise fallback to mapping
            product = config_line.product_id or field_to_product.get(field_name)
            
            # Use custom description if provided, otherwise use product name or field label
            if config_line.description:
                description = config_line.description
            elif product:
                description = product.name
            else:
                description = tribute_field_labels.get(field_name, field_name)
            
            line_vals = {
                'product_id': product.id if product else False,
                'name': description,
                'quantity': 1,
                'price_unit': amount,
            }
            
            if product and product.property_account_expense_id:
                line_vals['account_id'] = product.property_account_expense_id.id
            
            lines.append((0, 0, line_vals))
    
    else:
        # Include all non-zero tributes (default behavior)
        all_fields = [
            'amount_duties', 'amount_statistics', 'amount_vat', 'amount_vat_additional',
            'amount_income_tax', 'amount_gross_income', 'amount_taxes', 'amount_fees'
        ]
        
        for field_name in all_fields:configures en tabla

3. ✅ **Configure Tributes to Include** (tabla editable, solo si "Only Selected")
   - Vista de tabla con columnas:
     - **Sequence** (handle draggable) → Orden de líneas en factura
     - **Tribute Field** → Qué tributo incluir
     - **Override Product** → Opcional: forzar producto específico
     - **Include if Zero** → Checkbox: incluir aunque sea $0
     - **Custom Description** → Opcional: texto personalizado para línea
   - Editable inline (editable="bottom")
   - Drag & drop para reordenar
                line_vals = {
                    'product_id': product.id if product else False,
                    'name': product.name if product else tribute_field_labels.get(field_name, field_name),
                    'quantity': 1,
                    'price_unit': amount,
                }
                
                if product and product.property_account_expense_id:
                    line_vals['account_id'] = product.property_account_expense_id.id
                
                lines.append((0, 0, line_vals))
    
    return lines
```

---

## 🎯 Configuración desde UI

### **Ruta:** `Settings > General Settings > COMEX > Tribute Invoice Settings`

**Opciones configurables:**

1. ✅ **Auto-fill Tribute Invoice Lines** (checkbox)
   - Si está activo → Pre-llena líneas automáticamente
   - Si está inactivo → Factura en blanco

2. ✅ **Invoice Lines to Include** (cuando auto-fill activo)
   - **All Non-Zero Tributes** → Incluye todos los tributos > 0
   - **Only Selected Tributes** → Solo los que selecciones abajo

3. ✅ **Select Tributes** (many2many tags, solo si "Only Selected")
   - DIE, Statistics Fee, VAT, etc.
   - Multi-selección visual con tags

4. ✅ **Default Tribute Vendor** (Many2one)
   - AFIP, Aduana, Despachante, etc.
   - Opcional (puede quedar vacío)

5. ✅ **Default Document Type** (Many2one)
   - Tipo 66, Tipo 01, etc.
   - Opcional

---

## 📋 Flujo Usuario Final

1. **Configurar una vez** (Settings > COMEX):
   - ✅ Auto pre-llenar: ON
   - ✅ Incluir: All tributes
   - ✅ Vendor: AFIP
   - ✅ Doc Type: 66

2. **Uso diario** (Clearance Form):
   - Click "Create Tribute Invoice"
   - Formulario nativo abre con TODO pre-llenado
   - Usuario ajusta si necesita
   - Guardar → Done

---

## ⚡ Ventajas del Enfoque Parametrizable
+ orden |
| **Productos** | Auto-detectados | Override por tributo |
| **Descripciones** | Fijas | Personalizables por línea 
| Aspecto | Hardcoded | Parametrizable |
|---------|-----------|----------------|
| **Flexibilidad** | Fijo en código | Configurable por usuario |
| **Vendors** | Solo AFIP | Cualquier proveedor |
| **Doc Types** | Solo 66 | Cualquier tipo |
| **Líneas** | Todos los tributos | Selección específica |
| **Actualizaciones** | Cambios en código | Cambios en Settings |
| **Multi-company** | Un solo setup | Config por compañía |

---

¿Procedo con esta implementación parametrizable?

---

## 🎬 Conclusión

Este plan elimina **100% del hardcoding** y convierte todo el sistema en **completamente configurable desde la UI**. Los usuarios pueden:

- Usar productos existentes o crear nuevos
- Mapear cualquier producto a cualquier tributo
- Agregar fallbacks por keywords sin tocar código
- Auditar qué se parseó y ajustar configuración
- Soportar esquemas personalizados por compañía

**Sin modificar ni una línea de Python para adaptar a nuevos esquemas de tributos.**

---

**¿Procedo con la implementación de Fase 1 (MVP)?**
