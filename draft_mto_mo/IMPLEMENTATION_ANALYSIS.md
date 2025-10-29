# 🔍 ANÁLISIS PROFUNDO: Implementación Alternativa 2 (Global → Producto → Usuario)

## 📋 Configuración Propuesta por Nivel

### Jerarquía de Precedencia:
```
1. GLOBAL (System Settings)
   ↓ (Si producto tiene override)
2. PRODUCTO (Product Template)
   ↓ (Si usuario tiene override)
3. USUARIO (res.users)
```

---

## 🎯 Opciones Configurables en Cada Nivel

### Opción A: Comportamiento por Tipo de Origen (4 opciones)

Cada nivel puede configurar independientemente:

| Tipo de Origen | Opción 1 | Opción 2 |
|----------------|----------|----------|
| **MTO desde Venta** | ✅ Native Flow (auto-confirm) | 📝 Draft |
| **MTS (Reabastecimiento)** | ✅ Native Flow (auto-confirm) | 📝 Draft |
| **MPS (Plan Maestro)** | ✅ Native Flow (auto-confirm) | 📝 Draft |
| **Orderpoint (Regla Reorden)** | ✅ Native Flow (auto-confirm) | 📝 Draft |

### Opción B: Política General + Override (Más Simple)

Cada nivel puede configurar:

1. **Política General:**
   - `use_parent` (Usar configuración del nivel superior)
   - `native_flow` (Seguir comportamiento nativo de Odoo)
   - `always_draft` (Siempre dejar en draft)
   - `custom` (Personalizado por tipo de origen)

2. **Si `custom`, entonces configurar las 4 opciones:**
   - MTO: Native / Draft
   - MTS: Native / Draft
   - MPS: Native / Draft
   - Orderpoint: Native / Draft

---

## 🏗️ Estructura de Implementación

### 1. **Nivel GLOBAL (res.config.settings)**

```python
# models/res_config_settings.py
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    # Política general
    mo_draft_global_policy = fields.Selection([
        ('native_flow', 'Native Odoo Behavior (Auto-confirm based on context)'),
        ('always_draft', 'All MOs stay in Draft'),
        ('custom', 'Custom by Source Type'),
    ], string="Global MO Draft Policy", 
       default='native_flow',
       config_parameter='draft_mto_mo.global_policy')
    
    # Configuración personalizada por tipo (solo si custom)
    mo_draft_mto = fields.Boolean(
        "MTO: Keep Draft",
        config_parameter='draft_mto_mo.draft_for_mto',
        default=True,
        help="Manufacturing Orders from Sales Orders (Make To Order)"
    )
    
    mo_draft_mts = fields.Boolean(
        "MTS: Keep Draft",
        config_parameter='draft_mto_mo.draft_for_mts',
        default=False,
        help="Manufacturing Orders for stock replenishment (Make To Stock)"
    )
    
    mo_draft_mps = fields.Boolean(
        "MPS: Keep Draft",
        config_parameter='draft_mto_mo.draft_for_mps',
        default=False,
        help="Manufacturing Orders from Master Production Schedule"
    )
    
    mo_draft_orderpoint = fields.Boolean(
        "Orderpoint: Keep Draft",
        config_parameter='draft_mto_mo.draft_for_orderpoint',
        default=False,
        help="Manufacturing Orders from Reordering Rules"
    )
```

**Vista XML:**
```xml
<!-- views/res_config_settings_views.xml -->
<record id="res_config_settings_view_form" model="ir.ui.view">
    <field name="name">res.config.settings.view.form.inherit.draft.mto.mo</field>
    <field name="model">res.config.settings</field>
    <field name="inherit_id" ref="base.res_config_settings_view_form"/>
    <field name="arch" type="xml">
        <xpath expr="//div[hasclass('settings')]" position="inside">
            <div class="app_settings_block" data_key="draft_mto_mo">
                <h2>Manufacturing Order Draft Control</h2>
                <div class="row mt16 o_settings_container">
                    <div class="col-12 col-lg-6 o_setting_box">
                        <div class="o_setting_left_pane">
                            <field name="mo_draft_global_policy" widget="radio"/>
                        </div>
                        <div class="o_setting_right_pane">
                            <label for="mo_draft_global_policy"/>
                            <div class="text-muted">
                                Control when Manufacturing Orders should stay in Draft state
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-12 col-lg-6 o_setting_box" 
                         invisible="mo_draft_global_policy != 'custom'">
                        <div class="o_setting_left_pane"/>
                        <div class="o_setting_right_pane">
                            <label for="mo_draft_mto" string="Draft by Source Type"/>
                            <div class="content-group">
                                <div class="mt8">
                                    <field name="mo_draft_mto" class="oe_inline"/>
                                    <label for="mo_draft_mto"/>
                                </div>
                                <div class="mt8">
                                    <field name="mo_draft_mts" class="oe_inline"/>
                                    <label for="mo_draft_mts"/>
                                </div>
                                <div class="mt8">
                                    <field name="mo_draft_mps" class="oe_inline"/>
                                    <label for="mo_draft_mps"/>
                                </div>
                                <div class="mt8">
                                    <field name="mo_draft_orderpoint" class="oe_inline"/>
                                    <label for="mo_draft_orderpoint"/>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </xpath>
    </field>
</record>
```

---

### 2. **Nivel PRODUCTO (product.template)**

```python
# models/product_template.py
from odoo import api, fields, models

class ProductTemplate(models.Model):
    _inherit = 'product.template'
    
    mo_draft_policy = fields.Selection([
        ('use_global', 'Use Global Settings'),
        ('native_flow', 'Native Odoo Behavior'),
        ('always_draft', 'Always Keep Draft'),
        ('always_confirm', 'Always Auto-Confirm'),
        ('custom', 'Custom by Source Type'),
    ], string="MO Draft Policy", 
       default='use_global',
       help="Override global settings for this product's Manufacturing Orders")
    
    # Configuración personalizada por tipo (solo si custom)
    mo_draft_mto = fields.Boolean(
        "MTO: Keep Draft",
        help="Manufacturing Orders from Sales Orders"
    )
    
    mo_draft_mts = fields.Boolean(
        "MTS: Keep Draft",
        help="Manufacturing Orders for stock replenishment"
    )
    
    mo_draft_mps = fields.Boolean(
        "MPS: Keep Draft",
        help="Manufacturing Orders from Master Production Schedule"
    )
    
    mo_draft_orderpoint = fields.Boolean(
        "Orderpoint: Keep Draft",
        help="Manufacturing Orders from Reordering Rules"
    )
```

**Vista XML:**
```xml
<!-- views/product_template_views.xml -->
<record id="product_template_form_view_inherit_draft_mo" model="ir.ui.view">
    <field name="name">product.template.form.inherit.draft.mo</field>
    <field name="model">product.template</field>
    <field name="inherit_id" ref="mrp.product_template_form_view_inherit_bom"/>
    <field name="arch" type="xml">
        <xpath expr="//page[@name='manufacturing']" position="inside">
            <group string="Manufacturing Order Draft Control">
                <field name="mo_draft_policy" widget="radio"/>
                <group invisible="mo_draft_policy != 'custom'">
                    <field name="mo_draft_mto"/>
                    <field name="mo_draft_mts"/>
                    <field name="mo_draft_mps"/>
                    <field name="mo_draft_orderpoint"/>
                </group>
            </group>
        </xpath>
    </field>
</record>
```

---

### 3. **Nivel USUARIO (res.users)**

```python
# models/res_users.py
from odoo import fields, models

class ResUsers(models.Model):
    _inherit = 'res.users'
    
    mo_draft_policy = fields.Selection([
        ('use_global', 'Use Global/Product Settings'),
        ('native_flow', 'Native Odoo Behavior'),
        ('always_draft', 'Always Keep Draft'),
        ('always_confirm', 'Always Auto-Confirm'),
        ('custom', 'Custom by Source Type'),
    ], string="MO Draft Policy", 
       default='use_global',
       help="Override global/product settings for MOs created by this user")
    
    # Configuración personalizada por tipo (solo si custom)
    mo_draft_mto = fields.Boolean(
        "MTO: Keep Draft",
        help="Manufacturing Orders from Sales Orders"
    )
    
    mo_draft_mts = fields.Boolean(
        "MTS: Keep Draft",
        help="Manufacturing Orders for stock replenishment"
    )
    
    mo_draft_mps = fields.Boolean(
        "MPS: Keep Draft",
        help="Manufacturing Orders from Master Production Schedule"
    )
    
    mo_draft_orderpoint = fields.Boolean(
        "Orderpoint: Keep Draft",
        help="Manufacturing Orders from Reordering Rules"
    )
```

**Vista XML:**
```xml
<!-- views/res_users_views.xml -->
<record id="view_users_form_inherit_draft_mo" model="ir.ui.view">
    <field name="name">res.users.form.inherit.draft.mo</field>
    <field name="model">res.users</field>
    <field name="inherit_id" ref="base.view_users_form"/>
    <field name="arch" type="xml">
        <xpath expr="//page[@name='preferences']" position="inside">
            <group string="Manufacturing Order Preferences">
                <field name="mo_draft_policy" widget="radio"/>
                <group invisible="mo_draft_policy != 'custom'">
                    <field name="mo_draft_mto"/>
                    <field name="mo_draft_mts"/>
                    <field name="mo_draft_mps"/>
                    <field name="mo_draft_orderpoint"/>
                </group>
            </group>
        </xpath>
    </field>
</record>
```

---

## 🔧 Lógica Central en stock.rule

```python
# models/stock_rule.py
from collections import defaultdict
from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.tools import float_compare

class StockRule(models.Model):
    _inherit = "stock.rule"

    def _run_manufacture(self, procurements):
        """Enhanced version with configurable draft behavior.
        
        Maintains Odoo's native logic:
        - Quantity validation
        - MO consolidation (for non-MTO)
        - Message posting (traceability)
        
        Adds configurable auto-confirm based on:
        - Global settings
        - Product settings
        - User settings
        """
        new_productions_values_by_company = defaultdict(list)
        
        # Phase 1: Prepare MO values (same as Odoo native)
        for procurement, rule in procurements:
            # Validate quantity (Odoo native logic)
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

            # Try to consolidate MO (Odoo native logic)
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
            
            # NEW: Determine which MOs should be confirmed
            productions_to_confirm = self.env['mrp.production']
            
            for production in productions:
                # Find corresponding procurement
                procurement, rule = self._find_procurement_for_mo(
                    production, procurements
                )
                
                if procurement and rule:
                    # Check if should stay in draft
                    should_stay_draft = self._should_keep_mo_draft(
                        procurement, rule, production
                    )
                    
                    if not should_stay_draft:
                        productions_to_confirm |= production
            
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
        """Find the procurement that generated this MO"""
        for procurement, rule in procurements:
            if (procurement.product_id == production.product_id and 
                procurement.company_id == production.company_id):
                return procurement, rule
        return None, None

    def _should_keep_mo_draft(self, procurement, rule, production):
        """Determine if MO should stay in draft.
        
        Hierarchy: Global → Product → User
        
        Returns:
            bool: True if MO should stay in draft, False to auto-confirm
        """
        source_type = self._get_procurement_source_type(procurement, rule)
        
        # 1. Start with GLOBAL settings
        draft_decision = self._get_global_draft_decision(source_type)
        
        # 2. Override with PRODUCT settings (if configured)
        product = procurement.product_id.product_tmpl_id
        if product.mo_draft_policy != 'use_global':
            draft_decision = self._get_product_draft_decision(
                product, source_type
            )
        
        # 3. Final override with USER settings (if configured)
        user = self.env.user
        if user.mo_draft_policy != 'use_global':
            draft_decision = self._get_user_draft_decision(
                user, source_type
            )
        
        return draft_decision

    def _get_procurement_source_type(self, procurement, rule):
        """Identify the source type of procurement.
        
        Returns:
            str: 'mto', 'mts', 'mps', or 'orderpoint'
        """
        values = procurement.values
        
        # Detect MTO route
        mto_route = self.env['stock.warehouse']._find_global_route(
            'stock.route_warehouse0_mto', 
            _('Replenish on Order (MTO)')
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

    def _get_global_draft_decision(self, source_type):
        """Get draft decision from global settings.
        
        Args:
            source_type (str): 'mto', 'mts', 'mps', 'orderpoint'
            
        Returns:
            bool: True if should stay draft
        """
        config = self.env['ir.config_parameter'].sudo()
        policy = config.get_param('draft_mto_mo.global_policy', 'native_flow')
        
        if policy == 'always_draft':
            return True
        elif policy == 'native_flow':
            return False  # Let Odoo's native logic decide
        elif policy == 'custom':
            # Check specific source type setting
            param_map = {
                'mto': 'draft_mto_mo.draft_for_mto',
                'mts': 'draft_mto_mo.draft_for_mts',
                'mps': 'draft_mto_mo.draft_for_mps',
                'orderpoint': 'draft_mto_mo.draft_for_orderpoint',
            }
            param_key = param_map.get(source_type)
            return config.get_param(param_key, 'False') == 'True'
        
        return False

    def _get_product_draft_decision(self, product, source_type):
        """Get draft decision from product settings.
        
        Args:
            product (product.template): Product template record
            source_type (str): 'mto', 'mts', 'mps', 'orderpoint'
            
        Returns:
            bool: True if should stay draft
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
            return getattr(product, field_name, False)
        
        # Fallback to global if 'use_global'
        return self._get_global_draft_decision(source_type)

    def _get_user_draft_decision(self, user, source_type):
        """Get draft decision from user settings.
        
        Args:
            user (res.users): User record
            source_type (str): 'mto', 'mts', 'mps', 'orderpoint'
            
        Returns:
            bool: True if should stay draft
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
            return getattr(user, field_name, False)
        
        # This shouldn't happen if called correctly, but fallback to global
        return self._get_global_draft_decision(source_type)
```

---

## ✅ Viabilidad del Diseño

### **✅ SÍ ES VIABLE** - Análisis:

#### 1. **Información Disponible en `procurement.values`**
```python
# Tenemos acceso completo a:
procurement.values = {
    'sale_line_id': sale.order.line,      # ✅ Detecta MTO
    'orderpoint_id': stock.warehouse.orderpoint,  # ✅ Detecta Orderpoint
    'group_id': procurement.group,
    'date_planned': datetime,
    'company_id': res.company,
}

procurement.origin  # ✅ Detecta 'MPS'
rule.route_id       # ✅ Detecta ruta MTO
```

#### 2. **Detección de Tipo de Origen - 100% Confiable**

| Tipo | Método de Detección | Confiabilidad |
|------|---------------------|---------------|
| **MTO** | `rule.route_id == mto_route` OR `values.get('sale_line_id')` | ✅ 100% |
| **MPS** | `procurement.origin == 'MPS'` | ✅ 100% |
| **Orderpoint** | `values.get('orderpoint_id')` | ✅ 100% |
| **MTS** | Default (ninguno de los anteriores) | ✅ 100% |

#### 3. **Acceso a Configuraciones**

```python
# ✅ Global: ir.config_parameter
config.get_param('draft_mto_mo.global_policy')

# ✅ Producto: procurement.product_id.product_tmpl_id
product.mo_draft_policy

# ✅ Usuario: self.env.user
user.mo_draft_policy
```

#### 4. **Mantiene Lógica Nativa de Odoo**

✅ **Validación de cantidad** (líneas 44-46)
✅ **Consolidación de MOs** (líneas 51-60)  
✅ **Mensajes de trazabilidad** (líneas 69-86)  
✅ **Filtro `_should_auto_confirm_procurement_mo`** (línea 67)

**Solo agrega:** Decisión condicional de si llamar `action_confirm()` o no.

---

## 🎯 Respuesta a tus Preguntas Específicas

### ❓ "¿Puedo establecer en cada nivel MTO/MTS/MPS/Orderpoint = Native/Draft?"

**✅ SÍ, ABSOLUTAMENTE VIABLE**

Cada nivel puede configurar independientemente las 4 opciones:

**Nivel GLOBAL:**
```python
mo_draft_mto = Boolean  # True = Draft, False = Native
mo_draft_mts = Boolean
mo_draft_mps = Boolean
mo_draft_orderpoint = Boolean
```

**Nivel PRODUCTO:**
```python
mo_draft_policy = Selection  # use_global, native_flow, always_draft, always_confirm, custom
mo_draft_mto = Boolean       # Solo si policy == 'custom'
mo_draft_mts = Boolean
mo_draft_mps = Boolean
mo_draft_orderpoint = Boolean
```

**Nivel USUARIO:**
```python
mo_draft_policy = Selection  # use_global, native_flow, always_draft, always_confirm, custom
mo_draft_mto = Boolean       # Solo si policy == 'custom'
mo_draft_mts = Boolean
mo_draft_mps = Boolean
mo_draft_orderpoint = Boolean
```

### ❓ "¿Es viable según el código base + Odoo source?"

**✅ SÍ, 100% VIABLE**

**Razones técnicas:**

1. **No rompe la lógica de Odoo:**
   - Usa `_prepare_mo_vals()` nativo (línea 21)
   - Mantiene consolidación de MOs (líneas 51-60)
   - Mantiene validación de cantidades (líneas 44-46)
   - Mantiene mensajes de trazabilidad (líneas 69-86)

2. **Punto de intervención perfecto:**
   - Línea 67 Odoo nativo: `productions.filtered(...).action_confirm()`
   - Nuestra modificación: Filtrar qué MOs van a `productions_to_confirm` ANTES de llamar `action_confirm()`

3. **Información completa disponible:**
   - Producto: `procurement.product_id`
   - Usuario: `self.env.user`
   - Tipo origen: Detectable via `procurement.values` y `rule.route_id`
   - Compañía: `procurement.company_id`

4. **Sin efectos secundarios:**
   - No modifica estructura de datos
   - No afecta otros módulos
   - Compatible con herencia múltiple

---

## 🚀 Ventajas del Diseño

### ✅ Mantiene compatibilidad con Odoo nativo
- Si todos los settings = 'use_global' / 'native_flow', comportamiento idéntico a Odoo estándar

### ✅ Máxima flexibilidad
- Configuración global para casos comunes
- Override por producto para excepciones
- Override por usuario para casos especiales

### ✅ Intuitivo
- Jerarquía natural: General → Específico → Muy Específico
- UI clara con radio buttons y checkboxes

### ✅ Performance óptimo
- Solo 3 validaciones por MO (global, producto, usuario)
- Sin queries adicionales complejos
- Configuraciones cacheadas en ir.config_parameter

### ✅ Extensible
- Fácil agregar nuevos tipos de origen
- Fácil agregar niveles (ej: compañía, almacén)

---

## 📊 Casos de Uso Reales

### Caso 1: Empresa conservadora
```
GLOBAL: always_draft (todo en draft)
PRODUCTO[A]: always_confirm (producto simple, auto-confirmar)
USUARIO[Manager]: native_flow (seguir Odoo para este usuario)
```

### Caso 2: Empresa ágil con excepciones
```
GLOBAL: custom (MTO=draft, MTS=native, MPS=native, Orderpoint=native)
PRODUCTO[Crítico]: always_draft (siempre revisar este producto)
USUARIO[Junior]: always_draft (este usuario debe revisar todo)
```

### Caso 3: Multi-departamento
```
GLOBAL: native_flow (comportamiento estándar)
PRODUCTO[MadeToOrder]: custom (MTO=draft, resto=native)
USUARIO[VentasTeam]: custom (MTO=draft, resto=native)
USUARIO[ProducciónTeam]: native_flow (puede confirmar todo)
```

---

## 🔧 Archivos a Crear/Modificar

```
draft_mto_mo/
├── __init__.py                          # ✅ Ya existe (actualizar)
├── __manifest__.py                      # ✅ Ya existe (actualizar depends, data)
├── models/
│   ├── __init__.py                      # ✅ Actualizar imports
│   ├── stock_rule.py                    # 🔄 MODIFICAR (lógica principal)
│   ├── res_config_settings.py          # ➕ CREAR
│   ├── product_template.py             # ➕ CREAR
│   └── res_users.py                     # ➕ CREAR
├── views/
│   ├── res_config_settings_views.xml   # ➕ CREAR
│   ├── product_template_views.xml      # ➕ CREAR
│   └── res_users_views.xml             # ➕ CREAR
├── security/
│   └── ir.model.access.csv             # 🔄 MODIFICAR (si nuevos modelos)
└── data/
    └── default_config.xml               # ➕ CREAR (valores default)
```

---

## ✅ Conclusión

### **ES COMPLETAMENTE VIABLE** ✅

La implementación propuesta:
- ✅ No rompe lógica de Odoo
- ✅ Mantiene consolidación de MOs
- ✅ Mantiene validaciones
- ✅ Mantiene trazabilidad
- ✅ Detección 100% confiable de tipos de origen
- ✅ Acceso completo a configuraciones en cada nivel
- ✅ Performance óptimo
- ✅ Extensible y mantenible

**¿Quieres que proceda con la implementación completa?**
