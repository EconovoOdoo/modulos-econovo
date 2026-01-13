# ANÁLISIS: Términos de Pago COMEX vs account.payment.term

**Fecha**: 13 de Enero de 2026  
**Analista**: GitHub Copilot + Jose D. Leonett  
**Contexto**: Evaluación de idoneidad de `account.payment.term` para operaciones COMEX argentinas

---

## 1. PROBLEMA IDENTIFICADO

### 1.1 Observación del Usuario

> "En Argentina, la forma de pago de una operación de comex **no suelen ser días de crédito**,  
> sino **combinaciones de instrumento + momento**: TT Vista, CDI 180 días, L/C Anticipado, etc."

**Ejemplos reales**:
- **TT Anticipado 100%**: Pago por transferencia antes del embarque
- **TT Vista**: Pago por transferencia a la vista de documentos
- **L/C 180 días**: Carta de crédito con plazo de 180 días
- **CDI Vista**: Cash Against Documents a la vista
- **L/C Anticipado**: Carta de crédito con pago anticipado

### 1.2 Limitación de `account.payment.term`

El modelo nativo de Odoo `account.payment.term`:
```python
# En addons/account/models/account_payment_term.py
class AccountPaymentTerm(models.Model):
    _name = "account.payment.term"
    _description = 'Payment Terms'
    
    # Campos principales:
    name = fields.Char(string='Payment Terms', required=True)
    line_ids = fields.One2many('account.payment.term.line', 'payment_term_id')
    # Líneas definen: días, porcentaje, tipo de cálculo (fin de mes, días fijos, etc.)
```

**Limitaciones para COMEX**:
1. ❌ Diseñado para crédito doméstico (30 días, 60 días, etc.)
2. ❌ No contempla **instrumentos de pago** (TT, L/C, CDI, D/P, D/A)
3. ❌ No contempla **momento de pago** (Anticipado, Vista, Diferido)
4. ❌ No refleja **riesgo bancario vs riesgo directo**
5. ❌ No vincula con **documentación requerida** (BL, invoice, certificados)

---

## 2. TÉRMINOS DE PAGO INTERNACIONALES (ICC - UCP 600)

### 2.1 Clasificación por Instrumento

| Instrumento | Nombre Completo | Riesgo | Banco Interviene | Uso COMEX AR |
|-------------|-----------------|--------|------------------|--------------|
| **TT** | Telegraphic Transfer / Wire Transfer | Alto | No | ⭐⭐⭐⭐⭐ Muy común |
| **L/C** | Letter of Credit (Carta de Crédito) | Bajo | Sí | ⭐⭐⭐ Común |
| **D/P** | Documents against Payment | Medio | Sí (cobro) | ⭐⭐ Ocasional |
| **D/A** | Documents against Acceptance | Medio | Sí (cobro) | ⭐⭐ Ocasional |
| **OA** | Open Account (Cuenta Abierta) | Muy Alto | No | ⭐ Raro |
| **CIA** | Cash In Advance (Anticipado) | Muy Bajo | No | ⭐⭐⭐ Común |

### 2.2 Clasificación por Momento de Pago

| Momento | Descripción | Ventaja Importador | Ventaja Exportador |
|---------|-------------|-------------------|-------------------|
| **Anticipado** | 100% antes del embarque | ❌ Paga antes de recibir | ✅ Cobra antes de enviar |
| **Vista** | Al presentar documentos | 🟨 Paga al ver docs | 🟨 Cobra rápido |
| **Diferido 30/60/90/180 días** | Plazo post-embarque | ✅ Crédito sin interés | ❌ Espera cobro |
| **Contra entrega** | Al recibir mercadería | ✅ Paga tras inspección | ❌ Riesgo de no cobro |

### 2.3 Combinaciones Típicas en Argentina

| Término COMEX | Instrumento | Momento | Descripción | Uso |
|---------------|-------------|---------|-------------|-----|
| **TT Anticipado** | Wire | Anticipado | Pago previo al embarque | Proveedor nuevo/desconfianza |
| **TT Vista** | Wire | Vista | Pago contra presentación de BL | Muy común |
| **TT 30/60/90 días** | Wire | Diferido | Crédito post-embarque | Proveedor confiable |
| **L/C Vista** | L/C | Vista | Banco paga al ver docs conformes | Equilibrado |
| **L/C 180 días** | L/C | Diferido | Banco garantiza pago futuro | Importador necesita financiación |
| **CDI Vista** | D/P | Vista | Documentos contra pago | Alternativa a L/C |
| **CDI 90 días** | D/A | Diferido | Documentos contra aceptación | Menor costo que L/C |

---

## 3. RELACIÓN CON NORMATIVA ARGENTINA

### 3.1 BCRA - Acceso al Mercado de Cambios (MULC)

**Comunicación "A" vigente (2025-2026)**: Define plazos máximos para acceso a divisas según:
- **Tipo de bien** (posición arancelaria NCM)
- **Incoterm utilizado**
- **Instrumento de pago**

**Ejemplo de restricción**:
```
Importación de bienes de capital (NCM 84.xx):
- L/C o D/P: Acceso hasta 365 días
- TT directo: Acceso hasta 180 días
- Anticipado: Acceso inmediato (sin plazo de espera)
```

### 3.2 Impacto en el Sistema

El término de pago COMEX **NO ES OPCIONAL** - afecta:

1. **Flujo de caja**: Cuándo se necesita acceso a divisas
2. **Cumplimiento BCRA**: Plazo permitido para liquidar en MULC
3. **Costos financieros**: L/C tiene comisiones bancarias
4. **Riesgo crediticio**: TT directo vs L/C garantizada
5. **Documentación**: L/C exige cumplimiento estricto de términos

---

## 4. ¿SE ACUERDA CON PROVEEDOR O ENTE ESTATAL?

### 4.1 Negociación Comercial (Importador ↔ Exportador)

**SE ACUERDA CON PROVEEDOR** en la negociación comercial:

```
┌─────────────────────────────────────────────────────────────────┐
│                    NEGOCIACIÓN COMERCIAL                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. COTIZACIÓN INICIAL                                          │
│     Proveedor: "FOB Shanghai, TT 30 días"                       │
│                                                                 │
│  2. CONTRAPROPUESTA                                             │
│     Importador: "Prefiero L/C 180 días"                         │
│                                                                 │
│  3. ACUERDO FINAL (quedaen Proforma Invoice y PO)               │
│     "CIF Buenos Aires, L/C 180 días a la vista"                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Documento contractual**: Proforma Invoice o Commercial Invoice

### 4.2 Validación BCRA (Post-acuerdo)

El BCRA **NO DEFINE** el término de pago, pero **VALIDA** si cumple normativa:

```
┌─────────────────────────────────────────────────────────────────┐
│                    VALIDACIÓN BCRA (MULC)                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Importador solicita acceso a divisas                        │
│     Presenta: Invoice, BL, Despacho de Importación             │
│                                                                 │
│  2. BCRA verifica:                                              │
│     ✅ ¿NCM permitido para importación?                         │
│     ✅ ¿Plazo de pago dentro de límite para ese NCM?            │
│     ✅ ¿Instrumentodepagoválido (L/C, TT, etc.)?              │
│                                                                 │
│  3. Autoriza o rechaza acceso a MULC                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Conclusión**: Es un campo **negociado comercialmente**, pero **regulado por BCRA**.

---

## 5. ¿DEBE ESTAR EN LA PURCHASE ORDER?

### 5.1 Ubicación del Término de Pago en Documentos

| Documento | ¿Debe aparecer? | Razón |
|-----------|----------------|-------|
| **Proforma Invoice** | ✅ Sí (crítico) | Documento de negociación |
| **Purchase Order** | ✅ Sí (obligatorio) | Confirma términos acordados |
| **Commercial Invoice** | ✅ Sí (obligatorio) | Documento para despacho y pago |
| **Bill of Lading** | ⚠️ Puede (opcional) | A veces indica forma de pago |
| **Operación COMEX** | ✅ Sí (obligatorio) | Planificación MULC y flujo de caja |
| **Despacho de Importación** | ⚠️ No directamente | Se deriva del invoice |

### 5.2 Impacto en Purchase Order de Odoo

El `purchase.order` ya tiene `payment_term_id`:
```python
# En addons/purchase/models/purchase.py
class PurchaseOrder(models.Model):
    _name = "purchase.order"
    
    payment_term_id = fields.Many2one(
        'account.payment.term', 
        string='Payment Terms'
    )
```

**Problema**: Este campo está diseñado para días de crédito doméstico, no COMEX.

**Pregunta**: ¿Usamos el campo nativo pero con naming COMEX, o creamos campo específico?

---

## 6. PROPUESTAS DE IMPLEMENTACIÓN

### 🔵 PROPUESTA A: Campo Selection Simple (RÁPIDO)

**Ventajas**: ✅ Simple, ✅ Directo, ✅ Cubre 80% de casos  
**Desventajas**: ❌ No extensible, ❌ Mezcla instrumento+momento

```python
class ComexOperation(models.Model):
    _name = 'comex.operation'
    
    payment_method = fields.Selection([
        ('tt_advance', 'TT Anticipado 100%'),
        ('tt_sight', 'TT a la Vista'),
        ('tt_30', 'TT 30 días'),
        ('tt_60', 'TT 60 días'),
        ('tt_90', 'TT 90 días'),
        ('tt_180', 'TT 180 días'),
        ('lc_sight', 'L/C a la Vista'),
        ('lc_30', 'L/C 30 días'),
        ('lc_60', 'L/C 60 días'),
        ('lc_90', 'L/C 90 días'),
        ('lc_180', 'L/C 180 días'),
        ('dp_sight', 'D/P a la Vista'),
        ('da_30', 'D/A 30 días'),
        ('da_60', 'D/A 60 días'),
        ('da_90', 'D/A 90 días'),
        ('oa_30', 'Cuenta Abierta 30 días'),
        ('oa_60', 'Cuenta Abierta 60 días'),
    ], string="Forma de Pago COMEX", tracking=True)
```

**Vista Form**:
```xml
<group name="payment">
    <field name="payment_method" required="1"/>
</group>
```

**Limitaciones**:
- ❌ No permite "L/C 120 días" si no está en lista
- ❌ Difícil para reportes (agrupar por instrumento o por plazo)

---

### 🟢 PROPUESTA B: Dos Campos Separados (RECOMENDADO) ⭐

**Ventajas**: ✅ Flexible, ✅ Reportes fáciles, ✅ Extensible, ✅ Alineado con estándar internacional  
**Desventajas**: ⚠️ Dos campos en lugar de uno

```python
class ComexOperation(models.Model):
    _name = 'comex.operation'
    
    # === PAYMENT METHOD ===
    payment_instrument = fields.Selection([
        ('tt', 'Telegraphic Transfer (TT)'),
        ('lc', 'Letter of Credit (L/C)'),
        ('dp', 'Documents against Payment (D/P)'),
        ('da', 'Documents against Acceptance (D/A)'),
        ('oa', 'Open Account'),
        ('cash', 'Cash in Advance'),
    ], string="Instrumento de Pago", required=True, tracking=True,
       help="Medio de pago utilizado para la transacción internacional")
    
    payment_timing = fields.Selection([
        ('advance', 'Anticipado'),
        ('sight', 'A la Vista'),
        ('15days', '15 días'),
        ('30days', '30 días'),
        ('60days', '60 días'),
        ('90days', '90 días'),
        ('120days', '120 días'),
        ('180days', '180 días'),
        ('360days', '360 días'),
    ], string="Momento de Pago", required=True, tracking=True,
       help="Plazo para realizar el pago desde embarque o presentación de documentos")
    
    # Campo computado para display
    payment_terms_display = fields.Char(
        string="Términos de Pago",
        compute='_compute_payment_terms_display',
        store=True
    )
    
    @api.depends('payment_instrument', 'payment_timing')
    def _compute_payment_terms_display(self):
        for record in self:
            if record.payment_instrument and record.payment_timing:
                instrument = dict(record._fields['payment_instrument'].selection).get(record.payment_instrument)
                timing = dict(record._fields['payment_timing'].selection).get(record.payment_timing)
                record.payment_terms_display = f"{instrument} - {timing}"
            else:
                record.payment_terms_display = False
    
    # Validación BCRA
    @api.constrains('payment_instrument', 'payment_timing', 'hs_code_id')
    def _check_bcra_payment_limits(self):
        for record in self:
            if record.payment_timing == '360days' and record.payment_instrument == 'tt':
                raise ValidationError(_("BCRA restricts TT payments beyond 180 days for most NCM codes."))
```

**Vista Form**:
```xml
<group name="payment" string="Payment Terms">
    <group>
        <field name="payment_instrument" required="1"/>
        <field name="payment_timing" required="1"/>
    </group>
    <group>
        <field name="payment_terms_display" readonly="1" class="oe_inline oe_read_only"/>
    </group>
</group>
```

**Vista Tree**:
```xml
<field name="payment_terms_display" optional="show"/>
```

---

### 🟡 PROPUESTA C: Modelo Maestro Configurable (ENTERPRISE)

**Ventajas**: ✅ Máxima flexibilidad, ✅ Multi-compañía, ✅ Auditoría completa  
**Desventajas**: ❌ Complejidad alta, ❌ Overhead para casos simples

```python
class ComexPaymentTerm(models.Model):
    """Maestro de Términos de Pago COMEX"""
    _name = 'comex.payment.term'
    _description = 'COMEX Payment Terms'
    _order = 'sequence, name'
    
    name = fields.Char(string="Name", required=True)  # "L/C 180 días"
    code = fields.Char(string="Code", required=True)  # "LC180"
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    
    # Desglose
    instrument = fields.Selection([...], required=True)
    timing_type = fields.Selection([
        ('advance', 'Anticipado'),
        ('sight', 'A la Vista'),
        ('days', 'Días Fecha Fija'),
    ], required=True)
    days = fields.Integer(string="Días", help="Solo si timing_type=days")
    
    # Costos asociados
    bank_commission_pct = fields.Float(string="Comisión Bancaria %", 
                                       help="Ej: L/C = 0.15% del valor FOB")
    
    # Restricciones BCRA
    bcra_max_days = fields.Integer(string="Plazo Máximo BCRA")
    bcra_communication = fields.Char(string="Comunicación BCRA Aplicable")
    
    # Relación con account.payment.term (opcional)
    account_payment_term_id = fields.Many2one(
        'account.payment.term',
        string="Odoo Payment Term Equivalent",
        help="Para sincronizar vencimientos en facturas"
    )

class ComexOperation(models.Model):
    _name = 'comex.operation'
    
    payment_term_id = fields.Many2one(
        'comex.payment.term',
        string="Forma de Pago",
        required=True,
        tracking=True
    )
```

**Ventajas adicionales**:
- Administrador puede agregar nuevos términos sin código
- Multi-compañía (cada empresa puede tener sus propios términos)
- Auditoría completa de cambios

---

### 🔴 PROPUESTA D: Usar `account.payment.term` con Naming (NO RECOMENDADO)

**Idea**: Crear términos en `account.payment.term` con nombres tipo "L/C 180 días"

**Ventajas**: ✅ Usa campo nativo  
**Desventajas**: ❌❌❌ **FUERTEMENTE DESACONSEJADO**

**Razones**:
1. ❌ `account.payment.term` calcula vencimientos por porcentajes y días - no aplica a L/C
2. ❌ No tiene concepto de "instrumento bancario"
3. ❌ Confunde el sistema contable (invoices tendrán términos incorrectos)
4. ❌ No es extensible para BCRA validation

---

## 7. COMPARACIÓN DE PROPUESTAS

| Criterio | Propuesta A | Propuesta B ⭐ | Propuesta C | Propuesta D |
|----------|-------------|---------------|-------------|-------------|
| **Simplicidad** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| **Flexibilidad** | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ |
| **Reportes** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ |
| **Extensibilidad** | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ |
| **Costo Desarrollo** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| **Alineación ICC** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ |
| **Validación BCRA** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ |
| **Integración Odoo** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |

---

## 8. INTEGRACIÓN CON PURCHASE ORDER

### 8.1 Extender `purchase.order`

```python
class PurchaseOrderComex(models.Model):
    _inherit = 'purchase.order'
    
    # Agregar campo COMEX-specific
    comex_payment_instrument = fields.Selection(
        related='comex_operation_id.payment_instrument',
        string="Instrumento Pago COMEX",
        readonly=False,
        store=True
    )
    comex_payment_timing = fields.Selection(
        related='comex_operation_id.payment_timing',
        string="Plazo Pago COMEX",
        readonly=False,
        store=True
    )
    
    # Mantener payment_term_id nativo para facturas domésticas
    # (no se usa para COMEX)
```

### 8.2 Vista PO Extendida

```xml
<record id="purchase_order_form_comex" model="ir.ui.view">
    <field name="name">purchase.order.form.comex</field>
    <field name="model">purchase.order</field>
    <field name="inherit_id" ref="purchase.views_purchase_order_form"/>
    <field name="arch" type="xml">
        
        <!-- Agregar campos COMEX después de incoterm -->
        <field name="incoterm_id" position="after">
            <field name="comex_payment_instrument" 
                   invisible="not comex_operation_id"/>
            <field name="comex_payment_timing" 
                   invisible="not comex_operation_id"/>
        </field>
        
    </field>
</record>
```

---

## 9. RECOMENDACIÓN FINAL

### 🎯 **IMPLEMENTAR PROPUESTA B** (Dos Campos Separados)

**Justificación**:

1. ✅ **Balance perfecto** entre simplicidad y funcionalidad
2. ✅ **Alineado con estándares internacionales** (ICC, UCP 600)
3. ✅ **Fácil de reportar**: Group by instrument, group by timing
4. ✅ **Extensible**: Agregar más opciones sin cambiar estructura
5. ✅ **Validación BCRA**: Fácil implementar restricciones por combinación
6. ✅ **Integración PO**: Se puede relacionar con purchase.order sin conflicto
7. ✅ **UX clara**: Usuario entiende que son dos dimensiones separadas

### 📋 Plan de Implementación

**FASE 1: Modelo COMEX**
- Agregar `payment_instrument` y `payment_timing` a `comex.operation`
- Agregar `payment_terms_display` computado
- Agregar validación BCRA básica

**FASE 2: Vistas**
- Form view: Grupo "Payment Terms" con ambos campos
- Tree view: Campo computado `payment_terms_display`
- Smart button para ver detalle de costos bancarios (si aplica L/C)

**FASE 3: Integración PO**
- Extender `purchase.order` con campos related a operación COMEX
- Vista inherited para mostrar términos COMEX en PO

**FASE 4: Reportes**
- Report agrupado por instrumento
- Report agrupado por plazo
- Dashboard con distribución de riesgo (TT directo vs L/C)

---

## 10. PRÓXIMOS PASOS

**Esperando decisión del usuario**:

1. ¿Aprobar Propuesta B?
2. ¿Agregar campos adicionales? (Ej: banco emisor L/C, costo bancario)
3. ¿Implementar validaciones BCRA desde el inicio o en fase 2?
4. ¿Sincronizar con `account.payment.term` para invoices o mantener separado?

**Tiempo estimado de implementación**:
- Propuesta B (básica): ~2-3 horas
- Con validaciones BCRA: ~4-5 horas
- Con maestro de costos bancarios: ~6-8 horas
