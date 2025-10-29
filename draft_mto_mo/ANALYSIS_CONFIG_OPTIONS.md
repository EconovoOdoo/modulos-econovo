# 📋 Analysis: Configuration Options for Draft MO Control

## 🎯 Objetivo
Implementar control granular sobre cuándo las órdenes de fabricación deben quedar en borrador vs. confirmarse automáticamente.

---

## 🔍 Contexto Disponible en `procurement.values`

Según el código fuente de Odoo 17, el diccionario `procurement.values` contiene:

```python
{
    'company_id': company,
    'date_planned': date_planned,
    'group_id': procurement_group,
    'route_ids': routes,
    'warehouse_id': warehouse,
    'priority': priority,
    
    # Información de origen (si aplica):
    'sale_line_id': sale.order.line,      # Viene de venta
    'orderpoint_id': stock.warehouse.orderpoint,  # Reabastecimiento
    'move_dest_ids': stock.move,          # Movimiento destino
    
    # Otros contextos:
    'origin': 'SO001' | 'MPS' | 'WH/OP/00123',
}
```

Además, en `_run_manufacture()` tenemos acceso a:
- `procurement.product_id` - Producto específico
- `rule` - Regla de abastecimiento (stock.rule)
- `rule.route_id` - Ruta (MTO, MTS, etc.)
- `bom` - Lista de materiales

---

## 🏗️ ALTERNATIVA 1: Jerarquía Producto → Usuario → Global

**Orden de precedencia:** Producto > Usuario > Global

### Ventajas
✅ Máxima flexibilidad por producto (casos especiales)  
✅ Control individual por usuario (permisos/roles)  
✅ Fallback global para casos comunes

### Desventajas
❌ Puede volverse complejo de administrar  
❌ Conflictos potenciales entre configuraciones

### Casos de uso ideales
- Productos críticos que siempre requieren revisión manual
- Usuarios junior que necesitan validación antes de confirmar
- Configuración global para operación estándar

### Implementación

```python
# models/res_config_settings.py
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    mo_draft_global_policy = fields.Selection([
        ('always_draft', 'Always Draft'),
        ('always_confirm', 'Always Confirm'),
        ('by_source', 'By Source Type'),
    ], string="Global MO Policy", default='by_source')
    
    mo_draft_mto = fields.Boolean("Draft for MTO", default=True)
    mo_draft_mts = fields.Boolean("Draft for MTS", default=False)
    mo_draft_mps = fields.Boolean("Draft for MPS", default=False)
    mo_draft_orderpoint = fields.Boolean("Draft for Orderpoint", default=False)

# models/res_users.py
class ResUsers(models.Model):
    _inherit = 'res.users'
    
    mo_draft_policy = fields.Selection([
        ('use_global', 'Use Global Policy'),
        ('always_draft', 'Always Draft'),
        ('always_confirm', 'Always Confirm'),
        ('custom', 'Custom Rules'),
    ], string="MO Draft Policy", default='use_global')
    
    mo_draft_mto = fields.Boolean("Draft for MTO")
    mo_draft_mts = fields.Boolean("Draft for MTS")
    mo_draft_mps = fields.Boolean("Draft for MPS")
    mo_draft_orderpoint = fields.Boolean("Draft for Orderpoint")

# models/product_template.py
class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    mo_draft_policy = fields.Selection([
        ('use_global', 'Use Global/User Policy'),
        ('always_draft', 'Always Draft'),
        ('always_confirm', 'Always Confirm'),
        ('custom', 'Custom Rules'),
    ], string="MO Draft Policy", default='use_global')
    
    mo_draft_mto = fields.Boolean("Draft for MTO")
    mo_draft_mts = fields.Boolean("Draft for MTS")
    mo_draft_mps = fields.Boolean("Draft for MPS")
    mo_draft_orderpoint = fields.Boolean("Draft for Orderpoint")

# models/stock_rule.py
def _should_keep_mo_draft(self, procurement, rule, production):
    """Determine if MO should stay in draft based on hierarchy: Product > User > Global"""
    product = procurement.product_id.product_tmpl_id
    user = self.env.user
    
    # Detect source type
    source_type = self._get_procurement_source_type(procurement, rule)
    
    # 1. Check Product level
    if product.mo_draft_policy != 'use_global':
        if product.mo_draft_policy == 'always_draft':
            return True
        elif product.mo_draft_policy == 'always_confirm':
            return False
        elif product.mo_draft_policy == 'custom':
            return self._check_custom_policy(product, source_type)
    
    # 2. Check User level
    if user.mo_draft_policy != 'use_global':
        if user.mo_draft_policy == 'always_draft':
            return True
        elif user.mo_draft_policy == 'always_confirm':
            return False
        elif user.mo_draft_policy == 'custom':
            return self._check_custom_policy(user, source_type)
    
    # 3. Fallback to Global
    config = self.env['ir.config_parameter'].sudo()
    global_policy = config.get_param('draft_mto_mo.global_policy', 'by_source')
    
    if global_policy == 'always_draft':
        return True
    elif global_policy == 'always_confirm':
        return False
    else:  # by_source
        return self._check_custom_policy(config, source_type)

def _get_procurement_source_type(self, procurement, rule):
    """Identify source type of procurement"""
    values = procurement.values
    mto_route = self.env['stock.warehouse']._find_global_route('stock.route_warehouse0_mto', _('Replenish on Order (MTO)'))
    
    if rule.route_id == mto_route or values.get('sale_line_id'):
        return 'mto'
    elif procurement.origin == 'MPS':
        return 'mps'
    elif values.get('orderpoint_id'):
        return 'orderpoint'
    else:
        return 'mts'

def _check_custom_policy(self, record, source_type):
    """Check custom policy for specific source type"""
    field_map = {
        'mto': 'mo_draft_mto',
        'mts': 'mo_draft_mts',
        'mps': 'mo_draft_mps',
        'orderpoint': 'mo_draft_orderpoint',
    }
    field_name = field_map.get(source_type)
    if hasattr(record, field_name):
        return getattr(record, field_name)
    return False
```

---

## 🏗️ ALTERNATIVA 2: Jerarquía Global → Producto → Usuario

**Orden de precedencia:** Global > Producto > Usuario

### Ventajas
✅ Configuración general primero (más intuitivo)  
✅ Override específico por producto cuando sea necesario  
✅ Control fino por usuario al final

### Desventajas
❌ Usuario puede sobrescribir configuraciones de producto crítico  
❌ Menos coherencia en casos especiales

### Casos de uso ideales
- Organización con política estándar clara
- Productos normales con excepciones menores
- Control por usuario para casos edge

### Lógica de decisión

```python
def _should_keep_mo_draft(self, procurement, rule, production):
    """Hierarchy: Global > Product > User"""
    source_type = self._get_procurement_source_type(procurement, rule)
    
    # 1. Start with Global
    draft_status = self._get_global_policy(source_type)
    
    # 2. Override with Product (if configured)
    product = procurement.product_id.product_tmpl_id
    if product.mo_draft_policy != 'use_global':
        draft_status = self._get_product_policy(product, source_type)
    
    # 3. Final override with User (if configured)
    user = self.env.user
    if user.mo_draft_policy != 'use_global':
        draft_status = self._get_user_policy(user, source_type)
    
    return draft_status
```

---

## 🏗️ ALTERNATIVA 3: Jerarquía Ruta → Producto → Compañía → Usuario

**Orden de precedencia:** Ruta (stock.rule) > Producto > Compañía > Usuario

### Ventajas
✅ Control a nivel de ruta de abastecimiento (más específico al flujo)  
✅ Multi-compañía considerado  
✅ Alineado con la arquitectura de Odoo (rutas son fundamentales)

### Desventajas
❌ Más complejo de configurar  
❌ Usuarios deben entender rutas de stock

### Casos de uso ideales
- Multi-almacén con diferentes políticas
- Multi-compañía con regulaciones diferentes
- Flujos complejos con muchas rutas personalizadas

### Implementación

```python
# models/stock_rule.py
class StockRule(models.Model):
    _inherit = 'stock.rule'
    
    mo_draft_policy = fields.Selection([
        ('use_default', 'Use Default Policy'),
        ('always_draft', 'Always Draft'),
        ('always_confirm', 'Always Confirm'),
    ], string="MO Draft Policy", default='use_default')

# models/res_company.py
class ResCompany(models.Model):
    _inherit = 'res.company'
    
    mo_draft_policy = fields.Selection([
        ('always_draft', 'Always Draft'),
        ('always_confirm', 'Always Confirm'),
        ('by_source', 'By Source Type'),
    ], default='by_source')
    
    mo_draft_mto = fields.Boolean("Draft for MTO", default=True)
    mo_draft_mts = fields.Boolean("Draft for MTS", default=False)
    mo_draft_mps = fields.Boolean("Draft for MPS", default=False)
    mo_draft_orderpoint = fields.Boolean("Draft for Orderpoint", default=False)

# Lógica de decisión
def _should_keep_mo_draft(self, procurement, rule, production):
    """Hierarchy: Route > Product > Company > User"""
    source_type = self._get_procurement_source_type(procurement, rule)
    
    # 1. Check Route level
    if rule.mo_draft_policy != 'use_default':
        if rule.mo_draft_policy == 'always_draft':
            return True
        elif rule.mo_draft_policy == 'always_confirm':
            return False
    
    # 2. Check Product level
    product = procurement.product_id.product_tmpl_id
    if product.mo_draft_policy != 'use_global':
        return self._get_product_policy(product, source_type)
    
    # 3. Check Company level
    company = procurement.company_id
    if company.mo_draft_policy == 'always_draft':
        return True
    elif company.mo_draft_policy == 'always_confirm':
        return False
    else:  # by_source
        return self._get_company_source_policy(company, source_type)
    
    # 4. Fallback to User
    user = self.env.user
    if user.mo_draft_policy != 'use_global':
        return self._get_user_policy(user, source_type)
    
    return False  # Default: confirm
```

---

## 🏗️ ALTERNATIVA 4: Matriz de Decisión (Avanzado)

**Sistema de puntuación con múltiples factores**

### Ventajas
✅ Máxima flexibilidad  
✅ Considera múltiples dimensiones simultáneamente  
✅ Extensible con nuevos criterios

### Desventajas
❌ Muy complejo de configurar  
❌ Difícil de debuggear  
❌ Puede ser overkill

### Factores considerados
1. **Tipo de origen** (MTO, MTS, MPS, Orderpoint) - Peso: 30%
2. **Producto** (categoría, valor, criticidad) - Peso: 25%
3. **Usuario** (rol, experiencia, permisos) - Peso: 20%
4. **Compañía** (política general) - Peso: 15%
5. **Contexto** (urgencia, stock disponible, BOM complejidad) - Peso: 10%

### Implementación

```python
# models/mo_draft_decision_matrix.py
class MoDraftDecisionMatrix(models.Model):
    _name = 'mo.draft.decision.matrix'
    _description = 'MO Draft Decision Matrix'
    
    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    
    # Conditions (domain-based)
    product_category_ids = fields.Many2many('product.category', string='Product Categories')
    product_ids = fields.Many2many('product.product', string='Specific Products')
    source_types = fields.Selection([
        ('mto', 'MTO'),
        ('mts', 'MTS'),
        ('mps', 'MPS'),
        ('orderpoint', 'Orderpoint'),
    ], string='Source Types')
    user_group_ids = fields.Many2many('res.groups', string='User Groups')
    company_ids = fields.Many2many('res.company', string='Companies')
    
    # Additional filters
    min_product_value = fields.Float(string='Min Product Value')
    max_product_value = fields.Float(string='Max Product Value')
    bom_complexity_threshold = fields.Integer(string='BOM Complexity Threshold', help='Number of components')
    
    # Decision
    action = fields.Selection([
        ('draft', 'Keep Draft'),
        ('confirm', 'Auto Confirm'),
    ], required=True, default='draft')
    
    # Priority/Weight
    priority = fields.Integer(default=50, help='Higher priority = evaluated first')

# Logic
def _should_keep_mo_draft(self, procurement, rule, production):
    """Advanced decision matrix"""
    # Get all active rules sorted by priority
    matrix_rules = self.env['mo.draft.decision.matrix'].search([
        ('active', '=', True)
    ], order='priority desc, sequence asc')
    
    context = self._build_decision_context(procurement, rule, production)
    
    for matrix_rule in matrix_rules:
        if self._matches_rule(matrix_rule, context):
            return matrix_rule.action == 'draft'
    
    # Default fallback
    return False

def _build_decision_context(self, procurement, rule, production):
    """Build context dict for decision"""
    product = procurement.product_id
    user = self.env.user
    source_type = self._get_procurement_source_type(procurement, rule)
    
    return {
        'product': product,
        'product_category': product.categ_id,
        'product_value': product.standard_price,
        'source_type': source_type,
        'user': user,
        'user_groups': user.groups_id,
        'company': procurement.company_id,
        'bom': production.bom_id,
        'bom_complexity': len(production.bom_id.bom_line_ids) if production.bom_id else 0,
        'origin': procurement.origin,
        'priority': procurement.priority,
    }

def _matches_rule(self, matrix_rule, context):
    """Check if context matches rule conditions"""
    # Product category check
    if matrix_rule.product_category_ids and context['product_category'] not in matrix_rule.product_category_ids:
        return False
    
    # Specific product check
    if matrix_rule.product_ids and context['product'] not in matrix_rule.product_ids:
        return False
    
    # Source type check
    if matrix_rule.source_types and context['source_type'] != matrix_rule.source_types:
        return False
    
    # User groups check
    if matrix_rule.user_group_ids and not (context['user_groups'] & matrix_rule.user_group_ids):
        return False
    
    # Company check
    if matrix_rule.company_ids and context['company'] not in matrix_rule.company_ids:
        return False
    
    # Product value range
    if matrix_rule.min_product_value and context['product_value'] < matrix_rule.min_product_value:
        return False
    if matrix_rule.max_product_value and context['product_value'] > matrix_rule.max_product_value:
        return False
    
    # BOM complexity
    if matrix_rule.bom_complexity_threshold and context['bom_complexity'] < matrix_rule.bom_complexity_threshold:
        return False
    
    return True
```

---

## 🏗️ ALTERNATIVA 5: Híbrido Simple (Recomendado para MVP)

**Combinación pragmática: Global + Producto + Regla**

### Ventajas
✅ Balance entre simplicidad y flexibilidad  
✅ Cubre 80% de casos de uso  
✅ Fácil de entender y mantener  
✅ Alineado con arquitectura Odoo

### Implementación

```python
# models/res_config_settings.py
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    mo_draft_for_mto = fields.Boolean(
        "Keep MO Draft for MTO",
        config_parameter='draft_mto_mo.draft_for_mto',
        default=True
    )
    mo_draft_for_mts = fields.Boolean(
        "Keep MO Draft for MTS",
        config_parameter='draft_mto_mo.draft_for_mts',
        default=False
    )
    mo_draft_for_mps = fields.Boolean(
        "Keep MO Draft for MPS",
        config_parameter='draft_mto_mo.draft_for_mps',
        default=False
    )
    mo_draft_for_orderpoint = fields.Boolean(
        "Keep MO Draft for Reorder Rules",
        config_parameter='draft_mto_mo.draft_for_orderpoint',
        default=False
    )

# models/product_template.py
class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    mo_draft_override = fields.Selection([
        ('use_global', 'Use Global Settings'),
        ('always_draft', 'Always Keep Draft'),
        ('always_confirm', 'Always Auto-Confirm'),
    ], string="MO Draft Behavior", default='use_global',
       help="Override global settings for this product")

# models/stock_rule.py
class StockRule(models.Model):
    _inherit = 'stock.rule'
    
    mo_draft_override = fields.Selection([
        ('use_default', 'Use Default Policy'),
        ('force_draft', 'Force Draft'),
        ('force_confirm', 'Force Confirm'),
    ], string="MO Draft Override", default='use_default',
       help="Override default behavior for this route")

def _run_manufacture(self, procurements):
    """Enhanced version with configurable draft behavior"""
    new_productions_values_by_company = defaultdict(list)
    productions_to_confirm = self.env['mrp.production']
    
    for procurement, rule in procurements:
        # ... existing validation logic ...
        
        if not mo:
            new_productions_values_by_company[procurement.company_id.id].append(
                rule._prepare_mo_vals(*procurement, bom)
            )
    
    for company_id, productions_values in new_productions_values_by_company.items():
        productions = self.env['mrp.production'].with_user(SUPERUSER_ID).sudo()\
            .with_company(company_id).create(productions_values)
        
        # NEW: Determine which productions should be confirmed
        for production in productions:
            procurement = self._get_procurement_for_production(production, procurements)
            rule = self._get_rule_for_procurement(procurement, procurements)
            
            if not self._should_keep_mo_draft(procurement, rule, production):
                productions_to_confirm |= production
        
        # Confirm only selected productions
        productions_to_confirm.filtered(
            self._should_auto_confirm_procurement_mo
        ).action_confirm()
        
        # ... existing message posting logic ...
    
    return True

def _should_keep_mo_draft(self, procurement, rule, production):
    """Determine if MO should stay in draft"""
    # 1. Check Rule level override (highest priority for specific flows)
    if rule.mo_draft_override == 'force_draft':
        return True
    elif rule.mo_draft_override == 'force_confirm':
        return False
    
    # 2. Check Product level override
    product_tmpl = procurement.product_id.product_tmpl_id
    if product_tmpl.mo_draft_override == 'always_draft':
        return True
    elif product_tmpl.mo_draft_override == 'always_confirm':
        return False
    
    # 3. Fall back to Global settings by source type
    source_type = self._get_procurement_source_type(procurement, rule)
    config = self.env['ir.config_parameter'].sudo()
    
    param_map = {
        'mto': 'draft_mto_mo.draft_for_mto',
        'mts': 'draft_mto_mo.draft_for_mts',
        'mps': 'draft_mto_mo.draft_for_mps',
        'orderpoint': 'draft_mto_mo.draft_for_orderpoint',
    }
    
    param_key = param_map.get(source_type, 'draft_mto_mo.draft_for_mts')
    return config.get_param(param_key, 'False') == 'True'

def _get_procurement_source_type(self, procurement, rule):
    """Identify source type"""
    values = procurement.values
    mto_route = self.env['stock.warehouse']._find_global_route(
        'stock.route_warehouse0_mto', _('Replenish on Order (MTO)')
    )
    
    # Priority order for detection:
    if rule.route_id == mto_route or values.get('sale_line_id'):
        return 'mto'
    elif procurement.origin == 'MPS':
        return 'mps'
    elif values.get('orderpoint_id'):
        return 'orderpoint'
    else:
        return 'mts'
```

---

## 📊 Comparación de Alternativas

| Criterio | Alt 1<br>(Prod→User→Global) | Alt 2<br>(Global→Prod→User) | Alt 3<br>(Route→Prod→Co→User) | Alt 4<br>(Matrix) | Alt 5<br>(Hybrid) |
|----------|---------|---------|---------|---------|---------|
| **Complejidad** | Media | Media | Alta | Muy Alta | Baja |
| **Flexibilidad** | Alta | Alta | Muy Alta | Máxima | Media-Alta |
| **Facilidad Config** | Media | Alta | Baja | Muy Baja | Alta |
| **Performance** | Buena | Buena | Buena | Media | Muy Buena |
| **Mantenibilidad** | Media | Media | Baja | Muy Baja | Alta |
| **Casos de uso** | 90% | 85% | 95% | 100% | 80% |
| **Curva aprendizaje** | Media | Baja | Alta | Muy Alta | Baja |
| **Recomendado para** | Empresas medianas | Startups/PyMEs | Enterprise | Casos complejos | MVP/Mayoría |

---

## 🎯 Recomendación Final

### **Para la mayoría de casos: ALTERNATIVA 5 (Híbrido Simple)**

**Razones:**
1. ✅ Cubre el 80% de casos de uso reales
2. ✅ Fácil de configurar y entender
3. ✅ Alineado con arquitectura Odoo (rutas y productos)
4. ✅ Performance óptima (pocas validaciones)
5. ✅ Fácil de extender si se necesita más adelante

**Orden de precedencia sugerido:**
```
Regla (stock.rule) → Producto → Global (por tipo de origen)
```

**Flujo de decisión:**
```
¿La ruta tiene override? 
  ├─ Sí → Usar override de ruta
  └─ No → ¿El producto tiene override?
            ├─ Sí → Usar override de producto
            └─ No → Usar configuración global según tipo (MTO/MTS/MPS/Orderpoint)
```

### **Para casos enterprise complejos: ALTERNATIVA 3 o 4**

Si la empresa tiene:
- Múltiples compañías con regulaciones diferentes
- Flujos muy complejos con muchas rutas personalizadas
- Necesidad de auditoría y trazabilidad extrema

Entonces considerar Alternativa 3 (Route→Prod→Co→User) o 4 (Matrix).

---

## 🚀 Plan de Implementación Sugerido

### Fase 1: MVP (Alternativa 5)
- Configuración global por tipo de origen
- Override a nivel de producto
- Override a nivel de regla

### Fase 2: Extensión (si se necesita)
- Agregar nivel de usuario
- Agregar nivel de compañía

### Fase 3: Avanzado (si se justifica)
- Sistema de matriz de decisión
- Logs de decisiones
- Dashboard de análisis

---

## 📝 Estructura de Archivos Sugerida

```
draft_mto_mo/
├── models/
│   ├── __init__.py
│   ├── res_config_settings.py       # Configuración global
│   ├── product_template.py          # Override por producto
│   ├── stock_rule.py                # Override por ruta + lógica principal
│   └── mo_draft_decision_log.py     # (Opcional) Log de decisiones
├── views/
│   ├── res_config_settings_views.xml
│   ├── product_template_views.xml
│   └── stock_rule_views.xml
├── security/
│   └── ir.model.access.csv
└── data/
    └── default_config.xml           # Valores por defecto
```

---

**¿Quieres que implemente la Alternativa 5 (recomendada) o prefieres otra?**
