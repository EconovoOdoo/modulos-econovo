# 🏗️ ARQUITECTURA LIMPIA - ECONOVO USER WAREHOUSE RESTRICTION

**Fecha:** 2025-11-22  
**Autor:** Jose D. Leonett  
**Objetivo:** Arquitectura 100% independiente, sin referencias a módulos externos

---

## 📋 TABLA DE CONTENIDOS

1. [Eliminación de Referencias Externas](#eliminación-de-referencias-externas)
2. [Nueva Arquitectura de Grupos](#nueva-arquitectura-de-grupos)
3. [Lógica de Permisos Rediseñada](#lógica-de-permisos-rediseñada)
4. [Casos Edge y Soluciones](#casos-edge-y-soluciones)
5. [Implementación Python](#implementación-python)
6. [Record Rules Rediseñadas](#record-rules-rediseñadas)
7. [Plan de Migración](#plan-de-migración)

---

## 🗑️ ELIMINACIÓN DE REFERENCIAS EXTERNAS

### **Referencias a Eliminar:**

```python
# ❌ ELIMINAR de todos los archivos:
- "Cybrosys" / "cybrosys"
- "user_warehouse_restriction."
- "Cybrosys Technologies"
- "from Cybrosys"
- "Base (Cybrosys)"
- "Vishnu K P"
- "odoo@cybrosys.com"
- Comentarios de copyright Cybrosys
- Referencias a "Base module"
- "user_warehouse_restriction_group_user" (renombrar)
```

### **Archivos Afectados:**

1. `__manifest__.py` - Descripción, comentarios
2. `models/stock_picking.py` - Headers
3. `models/res_config_settings.py` - Headers, XML IDs
4. `models/stock_warehouse.py` - Comentarios
5. `models/res_users.py` - Comentarios
6. `models/stock_move.py` - Comentarios
7. `hooks.py` - Función migración, comentarios
8. `security/econovo_user_warehouse_restriction_groups.xml` - Comentarios, nombres
9. `security/econovo_user_warehouse_restriction_security.xml` - Comentarios
10. `ANALISIS_INCONSISTENCIAS.md` - TODO el archivo (archivo antiguo)

---

## 🎯 NUEVA ARQUITECTURA DE GRUPOS

### **Principios de Diseño:**

1. ✅ **Independencia Total:** Sin herencias externas
2. ✅ **Claridad Semántica:** Nombres que describen permisos
3. ✅ **Herencia Lógica:** Cada nivel añade permisos
4. ✅ **Seguridad por Defecto:** Nivel más restrictivo por defecto
5. ✅ **Bypass Administrativo:** Admins completamente excluidos

---

### **JERARQUÍA DE 6 NIVELES**

```
┌────────────────────────────────────────────────────────────┐
│                    PYRAMID OF ACCESS                        │
│                                                             │
│                  [0] UNRESTRICTED                           │
│                  (Administrators)                           │
│                  ▲ BYPASS ALL                               │
│                  │                                           │
│          ┌───────┴───────┐                                  │
│          │   [1] BASE    │                                  │
│          │   (Hidden)    │                                  │
│          │ Foundation    │                                  │
│          └───────┬───────┘                                  │
│                  │                                           │
│          ┌───────┴───────┐                                  │
│          │ [2] READ ONLY │                                  │
│          │  View Only    │                                  │
│          └───────┬───────┘                                  │
│                  │                                           │
│          ┌───────┴───────┐                                  │
│          │ [3] SEND ONLY │                                  │
│          │ (Dest Valid)  │                                  │
│          └───────┬───────┘                                  │
│                  │                                           │
│          ┌───────┴───────┐                                  │
│          │[4] BIDIRECTION│                                  │
│          │  (Hub WH)     │                                  │
│          └───────┬───────┘                                  │
│                  │                                           │
│          ┌───────┴───────┐                                  │
│          │ [5] FULL LOCK │                                  │
│          │   (DEFAULT)   │                                  │
│          └───────────────┘                                  │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

---

### **NIVEL 0: UNRESTRICTED (Admin Bypass)**

**XML ID:** `group_warehouse_unrestricted`

**Características:**
- NO es un grupo asignable directamente
- Auto-asignado a `base.group_system` vía `implied_ids`
- Record Rules NO tienen este grupo (bypass completo)
- Python Constraints revisan este grupo PRIMERO
- Usuario: Administrador del sistema

**Permisos:**
```python
permissions = {
    'view_all_warehouses': True,      # Incluso no asignados
    'view_all_locations': True,        # Sin blacklist
    'create_anywhere': True,           # Cualquier WH
    'modify_anywhere': True,           # Cualquier WH
    'cross_warehouse_unrestricted': True,  # WH1 → WH2 sin validar
    'bypass_transit_rules': True,      # No necesita tránsito
    'inventory_adjustments_anywhere': True,
    'quant_access_unrestricted': True
}
```

**Implementación:**
```xml
<record id="group_warehouse_unrestricted" model="res.groups">
    <field name="name">Warehouse - Unrestricted Access</field>
    <field name="category_id" ref="base.module_category_hidden"/>
</record>

<record id="base.group_system" model="res.groups">
    <field name="implied_ids" eval="[(4, ref('group_warehouse_unrestricted'))]"/>
</record>
```

**Python Check:**
```python
if self.env.su or user.has_group('econovo_user_warehouse_restriction.group_warehouse_unrestricted'):
    continue  # Skip ALL validation
```

---

### **NIVEL 1: BASE (Foundation)**

**XML ID:** `group_warehouse_base`

**Características:**
- Grupo OCULTO (category: hidden)
- NO asignable directamente a usuarios
- Solo heredado por otros grupos
- Activa funcionalidad del módulo
- Aplica Record Rules básicos

**Permisos:**
```python
permissions = {
    'view_assigned_warehouses_only': True,
    'view_assigned_locations_only': True,
    'blacklist_locations': True,  # user.location_ids
    'filter_picking_types': True,
    'filter_pickings': True,
    'no_cross_warehouse': False,  # Sin validación adicional
}
```

**Record Rules Aplicados:**
1. `stock.picking.type` - Filtrar por `warehouse_id.user_ids`
2. `stock.location` - Blacklist `user.location_ids`
3. `stock.warehouse` - Filtrar por `user_ids`
4. `stock.picking` - Filtrar por `warehouse_id.user_ids`

**Implementación:**
```xml
<record id="group_warehouse_base" model="res.groups">
    <field name="name">Warehouse - Base Restriction</field>
    <field name="category_id" ref="base.module_category_hidden"/>
</record>
```

---

### **NIVEL 2: READ ONLY**

**XML ID:** `group_warehouse_readonly`

**Características:**
- Primer grupo VISIBLE y asignable
- Hereda de `group_warehouse_base`
- Solo lectura en WH asignados
- Sin permisos de modificación

**Permisos:**
```python
permissions = {
    **group_warehouse_base.permissions,  # Hereda base
    'view': True,
    'create': False,
    'write': False,
    'unlink': False,
}
```

**Record Rules:**
```xml
<!-- TODOS los record rules con permisos SOLO lectura -->
<field name="perm_read" eval="True"/>
<field name="perm_write" eval="False"/>
<field name="perm_create" eval="False"/>
<field name="perm_unlink" eval="False"/>
```

**Casos de Uso:**
- Auditores
- Consultores externos
- Usuarios de reporting
- Observadores de calidad

**Implementación:**
```xml
<record id="group_warehouse_readonly" model="res.groups">
    <field name="name">Warehouse - Read Only</field>
    <field name="category_id" ref="base.module_category_inventory_inventory"/>
    <field name="implied_ids" eval="[(4, ref('group_warehouse_base'))]"/>
</record>
```

---

### **NIVEL 3: SEND ONLY (Destination Unrestricted)**

**XML ID:** `group_warehouse_send_only`

**Características:**
- Hereda de `group_warehouse_readonly`
- Valida SOLO origen (source)
- Destino SIN restricción
- Puede enviar a cualquier WH

**Permisos:**
```python
permissions = {
    **group_warehouse_readonly.permissions,  # Hereda
    'create': True,
    'write': True,
    'unlink': True,
    'send_to_any_destination': True,  # ✅ CLAVE
    'receive_from_assigned_only': True,  # ✅ RESTRICCIÓN
}
```

**Validación Python:**
```python
# SOLO valida SOURCE
if source_warehouse and source_warehouse not in allowed_warehouses:
    if not (source_warehouse.is_transit or location_id.is_transit):
        raise ValidationError("Cannot remove stock from unauthorized warehouse")

# NO valida destination (puede enviar a cualquiera)
```

**Matriz de Operaciones:**

| Operación | WH Asignado | Permitido | Razón |
|-----------|-------------|-----------|-------|
| WH1 → WH1 | WH1 | ✅ | Internal move OK |
| WH1 → WH2 | WH1 | ✅ | Send allowed |
| WH1 → WH3 | WH1 | ✅ | Send allowed |
| WH2 → WH1 | WH1 | ❌ | Cannot remove from WH2 |
| WH2 → WH3 | WH1 | ❌ | Cannot remove from WH2 |

**Casos de Uso:**
- Centros de distribución regional
- Warehouses que redistribuyen a retail
- Proveedores internos que envían a clientes

---

### **NIVEL 4: BIDIRECTIONAL (Hub Warehouses)**

**XML ID:** `group_warehouse_bidirectional`

**Características:**
- Hereda de `group_warehouse_send_only`
- Puede ENVIAR a cualquier WH
- Puede RECIBIR de cualquier WH
- Actúa como intermediario

**Permisos:**
```python
permissions = {
    **group_warehouse_send_only.permissions,  # Hereda
    'receive_from_any_warehouse': True,  # ✅ AÑADE
    'send_to_any_warehouse': True,  # Ya tenía
    'act_as_hub': True,  # ✅ NUEVO
}
```

**Validación Python:**
```python
# Valida que AL MENOS UNO (source O dest) sea warehouse asignado
involved_warehouses = [source_warehouse, dest_warehouse]
assigned_involved = any(wh in allowed_warehouses for wh in involved_warehouses if wh)

if not assigned_involved:
    # Ninguno de los dos es warehouse asignado
    if not (source_is_transit or dest_is_transit):
        raise ValidationError("At least source OR destination must be assigned warehouse")
```

**Matriz de Operaciones:**

| Operación | WH Asignado | Permitido | Razón |
|-----------|-------------|-----------|-------|
| WH1 → WH1 | WH1 | ✅ | Internal OK |
| WH1 → WH2 | WH1 | ✅ | Send OK (source asignado) |
| WH2 → WH1 | WH1 | ✅ | Receive OK (dest asignado) |
| WH2 → WH3 | WH1 | ❌ | Ni source ni dest asignado |

**Casos de Uso:**
- Hub warehouses centrales
- Cross-docking facilities
- Gestores logísticos inter-warehouse
- Coordinadores de tránsito

---

### **NIVEL 5: FULL LOCK (DEFAULT - Más Restrictivo)**

**XML ID:** `group_warehouse_full`

**Características:**
- Hereda de `group_warehouse_bidirectional`
- Valida SOURCE **Y** DESTINATION
- Nivel más restrictivo
- **DEFAULT para nuevos usuarios**

**Permisos:**
```python
permissions = {
    **group_warehouse_bidirectional.permissions,  # Hereda
    'receive_from_any_warehouse': False,  # ❌ REVOCA
    'send_to_any_warehouse': False,  # ❌ REVOCA
    'locked_to_assigned_only': True,  # ✅ RESTRICCIÓN MÁXIMA
}
```

**Validación Python:**
```python
# Valida SOURCE
if source_warehouse and source_warehouse not in allowed_warehouses:
    if not source_is_transit:
        raise ValidationError("Source not authorized")

# Valida DESTINATION
if dest_warehouse and dest_warehouse not in allowed_warehouses:
    if not dest_is_transit:
        raise ValidationError("Destination not authorized")
```

**Matriz de Operaciones:**

| Operación | WH Asignado | Permitido | Razón |
|-----------|-------------|-----------|-------|
| WH1 → WH1 | WH1 | ✅ | Ambos asignados |
| WH1 → WH2 | WH1 | ❌ | Dest NO asignado |
| WH2 → WH1 | WH1 | ❌ | Source NO asignado |
| WH1 → WH2 | WH1, WH2 | ✅ | Ambos asignados |

**Casos de Uso:**
- Operadores de warehouse estándar
- Personal de bodega local
- Usuarios que NO deben acceder otros WH
- **DEFAULT para seguridad**

---

## 🔒 LÓGICA DE PERMISOS REDISEÑADA

### **Problema Actual:**

```python
# ❌ PROBLEMA: Herencia causa conflicto
group_full.implied_ids = [group_send_only]
group_send_only.implied_ids = [group_readonly]
group_readonly.implied_ids = [group_base]

# Usuario con FULL tiene LOS 4 GRUPOS simultáneamente
user.groups_id = [group_base, group_readonly, group_send_only, group_full]

# Record Rules con OR lógico → Gana el MÁS PERMISIVO
# Usuario Full obtiene permisos de Send Only (más permisivo)
```

### **Solución: Validación en Orden Inverso**

```python
def _check_warehouse_permission(self):
    """Validates warehouse access in REVERSE inheritance order.
    
    CRITICAL: Check from MOST to LEAST restrictive to prevent bypass.
    """
    for move in self:
        user = self.env.user
        
        # [0] UNRESTRICTED - Bypass completo
        if self.env.su or user.has_group('group_warehouse_unrestricted'):
            continue
        
        # Si NO tiene ningún grupo de restricción, skip
        if not user.has_group('group_warehouse_base'):
            continue
        
        # Get allowed warehouses
        allowed = self.env['stock.warehouse'].search([('user_ids', 'in', user.id)])
        source_wh = move.location_id.warehouse_id
        dest_wh = move.location_dest_id.warehouse_id
        
        # ================================================================
        # CHECK FROM MOST TO LEAST RESTRICTIVE (reverse inheritance)
        # ================================================================
        
        # [5] FULL LOCK - Source AND Destination
        if user.has_group('group_warehouse_full'):
            self._validate_full_restriction(move, source_wh, dest_wh, allowed)
            continue  # ✅ Termina aquí, no evalúa niveles inferiores
        
        # [4] BIDIRECTIONAL - At least one (source OR dest)
        if user.has_group('group_warehouse_bidirectional'):
            self._validate_bidirectional(move, source_wh, dest_wh, allowed)
            continue
        
        # [3] SEND ONLY - Only source
        if user.has_group('group_warehouse_send_only'):
            self._validate_send_only(move, source_wh, allowed)
            continue
        
        # [2] READ ONLY - Should never create moves
        if user.has_group('group_warehouse_readonly'):
            raise ValidationError("Read Only users cannot create stock moves")
        
        # [1] BASE - No additional validation
        # (Record Rules ya filtran warehouses)
```

### **Validadores Específicos:**

```python
def _validate_full_restriction(self, move, source_wh, dest_wh, allowed):
    """Level 5: Both source AND destination must be allowed."""
    # Validate SOURCE
    if source_wh and source_wh not in allowed:
        if not (source_wh.is_transit_warehouse or move.location_id.is_transit_location):
            raise ValidationError(
                f"Full Restriction: Cannot remove stock from '{source_wh.name}'.\n"
                f"Allowed warehouses: {', '.join(allowed.mapped('name')) or 'None'}"
            )
    
    # Validate DESTINATION
    if dest_wh and dest_wh not in allowed:
        if not (dest_wh.is_transit_warehouse or move.location_dest_id.is_transit_location):
            raise ValidationError(
                f"Full Restriction: Cannot send stock to '{dest_wh.name}'.\n"
                f"Allowed warehouses: {', '.join(allowed.mapped('name')) or 'None'}"
            )

def _validate_bidirectional(self, move, source_wh, dest_wh, allowed):
    """Level 4: At least one (source OR dest) must be allowed."""
    source_ok = source_wh in allowed if source_wh else False
    dest_ok = dest_wh in allowed if dest_wh else False
    source_transit = (source_wh.is_transit_warehouse if source_wh else False) or move.location_id.is_transit_location
    dest_transit = (dest_wh.is_transit_warehouse if dest_wh else False) or move.location_dest_id.is_transit_location
    
    if not (source_ok or dest_ok or source_transit or dest_transit):
        raise ValidationError(
            f"Bidirectional: At least source OR destination must be assigned.\n"
            f"Source: {source_wh.name if source_wh else 'None'} ❌\n"
            f"Dest: {dest_wh.name if dest_wh else 'None'} ❌\n"
            f"Allowed: {', '.join(allowed.mapped('name')) or 'None'}"
        )

def _validate_send_only(self, move, source_wh, allowed):
    """Level 3: Only source validated (destination unrestricted)."""
    if source_wh and source_wh not in allowed:
        if not (source_wh.is_transit_warehouse or move.location_id.is_transit_location):
            raise ValidationError(
                f"Send Only: Cannot remove stock from '{source_wh.name}'.\n"
                f"You can only send FROM: {', '.join(allowed.mapped('name')) or 'None'}\n"
                f"Destination is unrestricted."
            )
```

---

## 🚨 CASOS EDGE Y SOLUCIONES

### **EDGE 1: Ubicaciones Virtuales (warehouse_id=False)**

**Problema:**
```python
# Ubicaciones virtuales de Odoo:
- Vendors (Suppliers)
- Customers
- Inventory Adjustments
- Production
- Scrapped

# TODAS tienen warehouse_id = False
```

**Impacto:**
```python
# ❌ Record Rule falla:
domain = [('location_id.warehouse_id.user_ids', 'in', user.id)]
# Si warehouse_id = False → user_ids está vacío → bloquea acceso
```

**Solución:**
```xml
<!-- Permitir ubicaciones SIN warehouse (virtuales) -->
<field name="domain_force">['|', '|',
    ('location_id.warehouse_id', '=', False),  <!-- ✅ Virtuales permitidas -->
    ('location_id.warehouse_id.user_ids', 'in', user.id),
    ('location_id.is_transit_location', '=', True)
]</field>
```

**Aplicar a:**
- `stock_quant_rule`
- `stock_move_rule_*`
- `stock_move_line_rule_*`

---

### **EDGE 2: Warehouses sin Usuarios Asignados**

**Escenario:**
```python
# Warehouse recién creado
wh = env['stock.warehouse'].create({'name': 'New WH', 'code': 'NEW'})
# wh.user_ids = []  (vacío)
```

**Problema:**
```python
# Usuario con restricciones NO puede verlo
domain = [('user_ids', 'in', user.id)]  # Retorna False
```

**Solución (Backward Compatibility):**
```xml
<field name="domain_force">['|', 
    ('user_ids', 'in', user.id),
    ('user_ids', '=', False)  <!-- ✅ Permite warehouses sin asignación -->
]</field>
```

**Consideración:**
- Aplicar SOLO a admins/instaladores
- Usuarios normales NO deberían ver WH vacíos (seguridad)

**Solución Alternativa:**
```python
# En stock_warehouse.create()
@api.model_create_multi
def create(self, vals_list):
    warehouses = super().create(vals_list)
    
    # Auto-asignar administradores a nuevos warehouses
    admin_group = self.env.ref('base.group_system')
    admins = self.env['res.users'].search([('groups_id', 'in', admin_group.id)])
    
    for warehouse in warehouses:
        if not warehouse.user_ids:
            warehouse.user_ids = [(6, 0, admins.ids)]
    
    return warehouses
```

---

### **EDGE 3: Multi-Compañía - Cambio de Contexto**

**Escenario:**
```python
# User1 tiene acceso a:
- Company A: WH1, WH2
- Company B: WH3

# Si habilita restricción en Company A solamente
```

**Problema Actual:**
```python
# res_config_settings.py
warehouses = self.env['stock.warehouse'].search([
    ('company_id', 'in', self.env.user.company_ids.ids)
])
# Auto-asigna WH1, WH2, WH3 (TODAS las compañías)
```

**Impacto:**
- Pierde granularidad por compañía
- No puede restringir en Company A y dejar abierto Company B

**Solución:**
```python
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    
    warehouse_restriction_scope = fields.Selection([
        ('current', 'Current Company Only'),
        ('all', 'All User Companies'),
    ], default='current', string="Restriction Scope")
    
    def set_values(self):
        super().set_values()
        if self.group_user_warehouse_restriction:
            # Determinar scope
            if self.warehouse_restriction_scope == 'current':
                domain = [('company_id', '=', self.env.company.id)]
            else:
                domain = [('company_id', 'in', self.env.user.company_ids.ids)]
            
            warehouses = self.env['stock.warehouse'].search(domain)
            # ... resto de lógica
```

---

### **EDGE 4: Herencia de Grupos - Record Rules Conflicto**

**Problema:**
```xml
<!-- Usuario con Full tiene TODOS los grupos por herencia -->
<record id="stock_move_rule_send_only">
    <field name="groups" eval="[(4, ref('group_warehouse_send_only'))]"/>
    <field name="domain_force">... solo source ...</field>
</record>

<record id="stock_move_rule_full">
    <field name="groups" eval="[(4, ref('group_warehouse_full'))]"/>
    <field name="domain_force">... source AND dest ...</field>
</record>

<!-- Odoo aplica OR entre reglas del mismo modelo -->
<!-- Usuario Full puede ver records de Send Only (más permisivo) -->
```

**Solución 1: Reglas Excluyentes**
```xml
<!-- SOLO aplicar regla a usuarios que NO tengan grupos superiores -->
<record id="stock_move_rule_send_only">
    <field name="domain_force">[
        '|', '|',
        ('location_id.warehouse_id.user_ids', 'in', user.id),
        ('location_id.warehouse_id.is_transit_warehouse', '=', True),
        '!', ('create_uid', 'in', ref('group_warehouse_full').users.ids)
    ]</field>
</record>
```

**Solución 2: UNA SOLA REGLA con Lógica Condicional**
```xml
<!-- Mejor approach: Una regla genérica que aplica a TODOS -->
<record id="stock_move_rule_generic">
    <field name="groups" eval="[(4, ref('group_warehouse_base'))]"/>
    <field name="domain_force">
        <!-- La validación específica se hace en Python Constraint -->
        ['|', '|', '|',
            ('location_id.warehouse_id', '=', False),
            ('location_id.warehouse_id.user_ids', 'in', user.id),
            ('location_id.warehouse_id.is_transit_warehouse', '=', True),
            ('location_id.is_transit_location', '=', True)
        ]
    </field>
</record>
```

**Enfoque Recomendado:** Solución 2
- Record Rules: Filtro básico (warehouses asignados + tránsito + virtuales)
- Python Constraints: Lógica específica por grupo

---

### **EDGE 5: Nuevos Usuarios Post-Instalación**

**Problema:**
```python
# post_init_hook solo se ejecuta UNA VEZ
# Usuarios creados DESPUÉS no reciben grupo automático
```

**Solución:**
```python
# models/res_users.py
class ResUsers(models.Model):
    _inherit = 'res.users'
    
    @api.model_create_multi
    def create(self, vals_list):
        """Auto-assign Full Restriction to new internal users."""
        users = super().create(vals_list)
        
        # Get groups
        full_group = self.env.ref(
            'econovo_user_warehouse_restriction.group_warehouse_full',
            raise_if_not_found=False
        )
        unrestricted_group = self.env.ref(
            'econovo_user_warehouse_restriction.group_warehouse_unrestricted',
            raise_if_not_found=False
        )
        
        for user in users:
            # Skip portal/public users
            if user.share:
                continue
            
            # Skip if already has unrestricted (admin)
            if unrestricted_group and unrestricted_group in user.groups_id:
                continue
            
            # Skip if already has Full group
            if full_group and full_group in user.groups_id:
                continue
            
            # Auto-assign Full Restriction (secure by default)
            if full_group:
                user.write({'groups_id': [(4, full_group.id)]})
                _logger.info(f"Auto-assigned Full Restriction to new user: {user.login}")
        
        return users
```

---

### **EDGE 6: Transit Locations vs Transit Warehouses**

**Diferencia:**
```python
# Transit Warehouse (is_transit_warehouse=True)
- TODO el warehouse es tránsito
- Todas sus ubicaciones accesibles
- Usado para warehouses completos de cross-docking

# Transit Location (is_transit_location=True)
- SOLO esa ubicación específica es tránsito
- Resto del warehouse puede estar restringido
- Usado para staging areas dentro de WH restringidos
```

**Validación Correcta:**
```python
def _is_transit(location, warehouse):
    """Check if location or warehouse is transit."""
    return (
        (warehouse and warehouse.is_transit_warehouse) or
        (location and location.is_transit_location)
    )

# En constraint:
source_transit = self._is_transit(move.location_id, source_warehouse)
dest_transit = self._is_transit(move.location_dest_id, dest_warehouse)
```

---

### **EDGE 7: Pickings Multi-Move (Diferentes Warehouses)**

**Escenario:**
```python
# Un picking con múltiples moves a diferentes destinos
picking = env['stock.picking'].create({...})
picking.move_ids = [
    (0, 0, {'location_id': WH1, 'location_dest_id': WH2}),
    (0, 0, {'location_id': WH1, 'location_dest_id': WH3}),
]
```

**Problema:**
- Constraint valida move por move
- Puede pasar algunos y fallar otros
- Picking queda en estado inconsistente

**Solución:**
```python
@api.constrains('location_id', 'location_dest_id')
def _check_warehouse_permission(self):
    """Validate ALL moves in transaction before committing."""
    errors = []
    
    for move in self:
        try:
            self._validate_single_move(move)
        except ValidationError as e:
            errors.append(f"Move {move.id}: {str(e)}")
    
    if errors:
        raise ValidationError(
            "Multiple moves failed validation:\n\n" + "\n".join(errors)
        )
```

---

## 📊 MATRIZ COMPARATIVA COMPLETA

| Feature | Unrestricted | Base | Read Only | Send Only | Bidirectional | Full |
|---------|--------------|------|-----------|-----------|---------------|------|
| **Ver WH asignados** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Ver WH NO asignados** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Ver todas locations** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Blacklist locations** | No aplica | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Crear picking WH asignado** | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ |
| **Modificar picking** | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ |
| **WH1 → WH1 (internal)** | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ |
| **WH1 → WH2 (send)** | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ |
| **WH2 → WH1 (receive)** | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ |
| **WH2 → WH3 (no involucrado)** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Ajustes inventario WH1** | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ |
| **Modificar quants WH2** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Acceso ubicaciones virtuales** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Usar tránsito** | No necesita | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Multi-compañía** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## 🎯 RESUMEN EJECUTIVO

### **Cambios Principales:**

1. ✅ **Eliminación Total de Referencias Externas**
   - Sin menciones a Cybrosys
   - Sin dependencias de `user_warehouse_restriction`
   - Módulo 100% autónomo

2. ✅ **6 Niveles de Acceso Jerárquicos**
   - Unrestricted (Admin) → Bypass total
   - Base (Hidden) → Fundación
   - Read Only → Solo lectura
   - Send Only → Redistribución
   - Bidirectional → Hubs
   - Full Lock → DEFAULT (seguro)

3. ✅ **Validación en Orden Inverso**
   - Revisa de MÁS a MENOS restrictivo
   - Evita bypass por herencia de grupos
   - Termina en primer match (continue)

4. ✅ **7 Casos Edge Resueltos**
   - Ubicaciones virtuales permitidas
   - Warehouses vacíos manejados
   - Multi-compañía con scope
   - Record Rules sin conflicto
   - Auto-asignación a nuevos usuarios
   - Diferenciación tránsito location/warehouse
   - Pickings multi-move validados

5. ✅ **Record Rules Optimizadas**
   - Una regla genérica por modelo
   - Python Constraint para lógica específica
   - Sin conflictos por herencia

### **Archivos a Modificar:**

1. `security/econovo_user_warehouse_restriction_groups.xml` - Rediseño completo
2. `security/econovo_user_warehouse_restriction_security.xml` - Simplificar
3. `models/stock_move.py` - Nueva lógica validación
4. `models/res_users.py` - Auto-asignación create()
5. `models/res_config_settings.py` - Scope multi-compañía
6. `hooks.py` - Eliminar migración Cybrosys
7. `__manifest__.py` - Nueva descripción
8. Todos los headers - Eliminar copyright Cybrosys

### **Testing Checklist:**

```python
tests = [
    # Unrestricted
    ('Admin can access all WH', 'PASS'),
    ('Admin bypass all validations', 'PASS'),
    
    # Read Only
    ('Can view assigned WH', 'PASS'),
    ('Cannot create picking', 'FAIL expected'),
    
    # Send Only
    ('WH1 → WH2 allowed', 'PASS'),
    ('WH2 → WH1 blocked', 'FAIL expected'),
    
    # Bidirectional
    ('WH1 → WH2 allowed', 'PASS'),
    ('WH2 → WH1 allowed', 'PASS'),
    ('WH2 → WH3 blocked', 'FAIL expected'),
    
    # Full
    ('WH1 → WH1 allowed', 'PASS'),
    ('WH1 → WH2 blocked', 'FAIL expected'),
    
    # Edge Cases
    ('Virtual locations work', 'PASS'),
    ('Transit WH accessible', 'PASS'),
    ('Empty WH visible to admin', 'PASS'),
    ('New user gets Full', 'PASS'),
]
```

---

**SIGUIENTE PASO:** ¿Procedo con la implementación de esta arquitectura limpia?
