# PLAN DE IMPLEMENTACIÓN: MATRIZ DE PERMISOS GRANULARES
# econovo_user_warehouse_restriction - Odoo 17

**Autor:** Jose D. Leonett  
**Fecha Inicio:** 2025-11-22  
**Estado:** 📋 PLANIFICACIÓN  
**Versión:** 2.0 (Refactorización completa)

---

## 📊 RESUMEN EJECUTIVO

### Objetivo
Transformar el módulo `econovo_user_warehouse_restriction` desde un sistema basado en **grupos heredados** (3 niveles: Unrestricted, Source Only, Full) hacia un sistema de **matriz de permisos granulares** por usuario/almacén.

### Problema Actual
- ✅ Sistema funcional con grupos heredados
- ❌ Complejidad: 3 grupos con herencia (Base → Source Only → Full)
- ❌ Inflexibilidad: Usuario tiene MISMO nivel de acceso en TODOS sus almacenes
- ❌ Conflictos: Record Rules con lógica OR debido a herencia
- ❌ Dependencia: Migración desde módulo Cybrosys con referencias legacy

### Solución Propuesta
**Matriz de Permisos Granulares** donde cada usuario puede tener permisos DIFERENTES en cada almacén:

```
┌─────────────────────┬──────────────────────────────────────┐
│ Usuario             │ Permisos por Almacén                 │
├─────────────────────┼──────────────────────────────────────┤
│ María González      │ WH1: Full Control                    │
│                     │ WH2: Solo Destino                    │
│                     │ WH3: Sin acceso                      │
├─────────────────────┼──────────────────────────────────────┤
│ Juan Pérez          │ WH1: Src+Dst+Inventario              │
│                     │ WH2: Solo lectura                    │
└─────────────────────┴──────────────────────────────────────┘
```

---

## 🎯 ARQUITECTURA PROPUESTA

### Nuevo Modelo: `warehouse.user.permission`

```python
class WarehouseUserPermission(models.Model):
    _name = 'warehouse.user.permission'
    _description = 'Granular warehouse permissions per user'
    _rec_name = 'user_id'
    
    # ============================================================
    # RELACIONES
    # ============================================================
    warehouse_id = fields.Many2one(
        'stock.warehouse', 
        required=True, 
        ondelete='cascade',
        string='Warehouse'
    )
    user_id = fields.Many2one(
        'res.users', 
        required=True, 
        ondelete='cascade',
        string='User',
        domain=[('groups_id', 'in', [ref('stock.group_stock_user')])]
    )
    
    # ============================================================
    # MODOS ESPECIALES (mutuamente excluyentes)
    # ============================================================
    full_control = fields.Boolean(
        string='Full Control',
        default=False,
        help='User has COMPLETE access to this warehouse.\n'
             'When enabled, all individual permissions below are ignored.'
    )
    
    view_only = fields.Boolean(
        string='View Only (Read-Only)',
        default=False,
        help='User can ONLY VIEW data in this warehouse.\n'
             'Cannot create, modify, or delete anything.'
    )
    
    # ============================================================
    # PERMISOS DE ACCESO AL ALMACÉN (Warehouse-level)
    # ============================================================
    allow_as_source = fields.Boolean(
        string='Use as Source',
        default=False,
        help='User can TAKE/SEND stock FROM this warehouse.\n'
             'Required for: Deliveries, Outbound Transfers'
    )
    
    allow_as_destination = fields.Boolean(
        string='Use as Destination',
        default=False,
        help='User can RECEIVE stock INTO this warehouse.\n'
             'Required for: Receipts, Inbound Transfers'
    )
    
    allow_inventory_adjustment = fields.Boolean(
        string='Inventory Adjustments',
        default=False,
        help='User can adjust stock quantities directly.\n'
             'WARNING: This bypasses source/destination validation.\n'
             'Grant only to trusted users (supervisors, accountants).'
    )
    
    # ============================================================
    # PERMISOS DE OPERACIONES (Operation-level)
    # ============================================================
    allow_create_picking = fields.Boolean(
        string='Create Transfers',
        default=False,
        help='User can CREATE new stock pickings/transfers.\n'
             'Note: User also needs Write permission to validate them.'
    )
    
    allow_write_picking = fields.Boolean(
        string='Modify/Validate Transfers',
        default=False,
        help='User can MODIFY and VALIDATE existing transfers.\n'
             'Includes changing products, quantities, and confirming operations.'
    )
    
    allow_delete_picking = fields.Boolean(
        string='Delete/Cancel Transfers',
        default=False,
        help='User can DELETE or CANCEL stock transfers.'
    )
    
    # ============================================================
    # RESTRICCIONES DE UBICACIONES (Location-level)
    # ============================================================
    blocked_location_ids = fields.Many2many(
        'stock.location',
        'warehouse_permission_blocked_location_rel',
        'permission_id',
        'location_id',
        string='Blocked Locations (Blacklist)',
        domain="[('warehouse_id', '=', warehouse_id)]",
        help='Locations within this warehouse that the user CANNOT access.\n'
             'BLACKLIST: User has access to all locations EXCEPT these.\n\n'
             'Example: User has access to WH1 but not WH1/QC or WH1/Quarantine.'
    )
    
    allow_transit = fields.Boolean(
        string='Access Transit Locations',
        default=True,
        help='User can use locations marked as Transit/Shared.\n'
             'Required for inter-warehouse transfers through shared spaces.'
    )
    
    # ============================================================
    # METADATA
    # ============================================================
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        related='warehouse_id.company_id',
        store=True,
        readonly=True
    )
    
    _sql_constraints = [
        ('unique_user_warehouse', 
         'UNIQUE(user_id, warehouse_id)',
         'A user can only have one permission record per warehouse!')
    ]
```

### Matriz Visual en Warehouse Form

```
═══════════════════════════════════════════════════════════════════════
WAREHOUSE: Central Buenos Aires
═══════════════════════════════════════════════════════════════════════

User             │Full│View│Src│Dst│Inv│Cr│Wr│Del│Transit│BlkLoc  │
─────────────────┼────┼────┼───┼───┼───┼──┼──┼───┼───────┼────────┤
María González   │ ✅ │ -  │ - │ - │ - │- │- │ - │  -    │  -     │
Juan Pérez       │ ❌ │ ❌ │ ✅│ ✅│ ✅│✅│✅│ ❌│  ✅   │ [+]    │
Pedro Sánchez    │ ❌ │ ❌ │ ❌│ ✅│ ❌│❌│❌│ ❌│  ❌   │  -     │
Laura Díaz       │ ❌ │ ✅ │ - │ - │ - │- │- │ - │  ❌   │  -     │
─────────────────┴────┴────┴───┴───┴───┴──┴──┴───┴───────┴────────┘

Legend:
  Full: Full Control (overrides all)
  View: View Only (read-only mode)
  Src: Use as Source
  Dst: Use as Destination
  Inv: Inventory Adjustments
  Cr: Create Pickings
  Wr: Write/Validate Pickings
  Del: Delete Pickings
  Transit: Access Transit Locations
  BlkLoc: Blocked Locations [+] = click to configure
```

---

## 🔧 COMPONENTES A MODIFICAR

### 1. MODELOS (models/)

#### **NUEVO:** `models/warehouse_user_permission.py`
- Modelo principal con matriz de permisos
- Validaciones de consistencia
- Helper methods para verificar permisos

#### **MODIFICAR:** `models/stock_warehouse.py`
- Agregar `user_permission_ids` (One2many)
- Eliminar/deprecar `user_ids` (Many2many)
- Deprecar `restrict_location` (ahora en permission)
- Eliminar campo `is_transit_warehouse` (ahora en location)
- Mantener helper method `action_open_users_view()`

#### **MODIFICAR:** `models/res_users.py`
- Eliminar/deprecar `location_ids` (ahora en permission.blocked_location_ids)
- Eliminar/deprecar `allowed_warehouse_ids` (ahora en permission)
- Eliminar/deprecar `restrict_location`
- Agregar computed field `warehouse_permission_ids`

#### **MODIFICAR:** `models/stock_move.py`
- Reescribir `_check_warehouse_transfer_permission()`
- Usar permission matrix en lugar de grupos
- Validar Src/Dst según permission flags

#### **MODIFICAR:** `models/stock_picking.py`
- Actualizar `_onchange_location_id()` para usar permission matrix
- Filtrar locations según blocked_location_ids

#### **MODIFICAR:** `models/stock_location.py`
- Mantener `is_transit_location` (sin cambios)

#### **MODIFICAR:** `models/res_config_settings.py`
- Simplificar `_onchange_group_user_warehouse_restriction()`
- Ya no necesita asignar user_ids a warehouses

### 2. SEGURIDAD (security/)

#### **MODIFICAR:** `security/econovo_user_warehouse_restriction_groups.xml`
- **ELIMINAR:** `group_warehouse_restriction_source_only`
- **ELIMINAR:** `group_warehouse_restriction_full`
- **MANTENER:** `user_warehouse_restriction_group_user` (base group)
- **MANTENER:** `group_warehouse_unrestricted` (admin bypass)

#### **NUEVO:** `security/ir.model.access.csv`
```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_warehouse_user_permission_user,warehouse.user.permission.user,model_warehouse_user_permission,stock.group_stock_user,1,0,0,0
access_warehouse_user_permission_manager,warehouse.user.permission.manager,model_warehouse_user_permission,stock.group_stock_manager,1,1,1,1
access_warehouse_user_permission_system,warehouse.user.permission.system,model_warehouse_user_permission,base.group_system,1,1,1,1
```

#### **MODIFICAR:** `security/econovo_user_warehouse_restriction_security.xml`
- **SIMPLIFICAR:** Record Rules (eliminar reglas por grupo)
- **NUEVA LÓGICA:** Filtrar por permission matrix en lugar de warehouse.user_ids

**Nuevos Record Rules:**

```xml
<!-- STOCK PICKING TYPE -->
<record id="operation_type_rule_users" model="ir.rule">
    <field name="domain_force">
        ['|', 
         ('warehouse_id', 'in', user.warehouse_permission_ids.warehouse_id.ids),
         ('warehouse_id', '=', False)]
    </field>
</record>

<!-- STOCK LOCATION -->
<record id="stock_location_rule_users" model="ir.rule">
    <field name="domain_force">
        ['|',
         ('id', 'not in', user.warehouse_permission_ids.blocked_location_ids.ids),
         ('is_transit_location', '=', True)]
    </field>
</record>

<!-- STOCK WAREHOUSE -->
<record id="stock_warehouse_rule_users" model="ir.rule">
    <field name="domain_force">
        [('id', 'in', user.warehouse_permission_ids.warehouse_id.ids)]
    </field>
</record>

<!-- STOCK PICKING -->
<record id="stock_picking_rule_users" model="ir.rule">
    <field name="domain_force">
        [('picking_type_id.warehouse_id', 'in', user.warehouse_permission_ids.warehouse_id.ids)]
    </field>
</record>

<!-- STOCK QUANT -->
<record id="stock_quant_rule_users" model="ir.rule">
    <field name="domain_force">
        ['|', '|',
         ('location_id.warehouse_id', 'in', user.warehouse_permission_ids.warehouse_id.ids),
         ('location_id.is_transit_location', '=', True),
         ('location_id.warehouse_id', '=', False)]
    </field>
</record>

<!-- STOCK MOVE (única regla, sin distinción por grupo) -->
<record id="stock_move_rule_users" model="ir.rule">
    <field name="domain_force">
        ['|',
         ('location_id.warehouse_id', 'in', user.warehouse_permission_ids.warehouse_id.ids),
         ('location_dest_id.warehouse_id', 'in', user.warehouse_permission_ids.warehouse_id.ids)]
    </field>
</record>

<!-- STOCK MOVE LINE (única regla, sin distinción por grupo) -->
<record id="stock_move_line_rule_users" model="ir.rule">
    <field name="domain_force">
        ['|',
         ('location_id.warehouse_id', 'in', user.warehouse_permission_ids.warehouse_id.ids),
         ('location_dest_id.warehouse_id', 'in', user.warehouse_permission_ids.warehouse_id.ids)]
    </field>
</record>
```

### 3. VISTAS (views/)

#### **NUEVO:** `views/warehouse_user_permission_views.xml`
- Form view para editar permiso individual
- Tree view editable in-line (para matriz en warehouse)

#### **MODIFICAR:** `views/stock_warehouse_views.xml`
- Reemplazar campo `user_ids` con `user_permission_ids`
- Agregar tree editable con columnas de permisos
- Botón para agregar usuarios rápido

#### **MODIFICAR:** `views/res_users_views.xml`
- Reemplazar pestaña "Restricted Location"
- Nueva pestaña "Warehouse Permissions" (resumen)

#### **MANTENER:** `views/stock_location_views.xml`
- Sin cambios (is_transit_location funciona igual)

#### **MODIFICAR:** `views/res_config_settings_views.xml`
- Actualizar help text del checkbox global
- Remover lógica de auto-assignment (ya no aplica)

### 4. HOOKS Y MIGRACIONES (hooks.py)

#### **MODIFICAR:** `hooks.py`
- **NUEVA FUNCIÓN:** `_migrate_to_permission_matrix(env)`
  - Leer warehouse.user_ids actuales
  - Crear registros en warehouse.user.permission
  - Mapear grupos a permisos:
    - `group_warehouse_unrestricted` → No crear registro (bypass)
    - `group_warehouse_restriction_full` → full_control=True
    - `group_warehouse_restriction_source_only` → allow_as_source=True
    - `user_warehouse_restriction_group_user` → allow_as_source=True, allow_as_destination=True
  - Migrar user.location_ids a permission.blocked_location_ids

- **MANTENER:** `_migrate_from_cybrosys_module(env)` (ejecutar antes de nueva migración)

- **NUEVA FUNCIÓN:** `_cleanup_legacy_groups(env)`
  - Eliminar usuarios de grupos deprecated
  - Logging de migración

### 5. MANIFEST (__manifest__.py)

#### **ACTUALIZAR:** Archivos data
```python
'data': [
    # Security
    'security/econovo_user_warehouse_restriction_groups.xml',
    'security/ir.model.access.csv',
    'security/econovo_user_warehouse_restriction_security.xml',
    
    # Views
    'views/warehouse_user_permission_views.xml',  # NUEVO
    'views/stock_warehouse_views.xml',
    'views/res_users_views.xml',
    'views/stock_location_views.xml',
    'views/res_config_settings_views.xml',
],
```

#### **ACTUALIZAR:** Version y description
```python
'version': '17.0.2.0.0',  # Cambio mayor (breaking changes)
'summary': 'Granular Warehouse Permissions Matrix per User',
```

---

## 📋 PLAN DE ACCIÓN DETALLADO

### FASE 1: PREPARACIÓN Y ANÁLISIS ✅
**Duración estimada:** Completado  
**Estado:** ✅ COMPLETADO

- [x] Analizar arquitectura actual (grupos heredados)
- [x] Identificar 10 funcionalidades NO consideradas
- [x] Detectar 6 inconsistencias lógicas
- [x] Diseñar matriz de permisos (10 columnas)
- [x] Validar coherencia lógica de columnas
- [x] Confirmar scope: Full Control POR ALMACÉN
- [x] Crear este documento de planificación

---

### FASE 2: MODELO DE DATOS 🔄
**Duración estimada:** 2-3 horas  
**Estado:** ⏸️ PENDIENTE APROBACIÓN

#### TASK 2.1: Crear modelo warehouse.user.permission
- [ ] Crear archivo `models/warehouse_user_permission.py`
- [ ] Implementar campos de relación (warehouse_id, user_id)
- [ ] Implementar modos especiales (full_control, view_only)
- [ ] Implementar permisos warehouse-level (Src, Dst, Inv)
- [ ] Implementar permisos operation-level (Cr, Wr, Del)
- [ ] Implementar restricciones location-level (blocked_location_ids, allow_transit)
- [ ] Agregar SQL constraint (unique_user_warehouse)
- [ ] Agregar dominio en user_id (solo stock users)
- [ ] Agregar dominio en blocked_location_ids (filtrar por warehouse)

#### TASK 2.2: Validaciones y constraints
- [ ] Constraint: view_only excluye permisos de escritura
- [ ] Constraint: full_control anula permisos individuales
- [ ] Onchange: Advertencia si Create sin Write
- [ ] Onchange: Auto-clear blocked_locations si full_control=True
- [ ] Compute: company_id desde warehouse

#### TASK 2.3: Helper methods
- [ ] `def check_permission(self, permission_type)`
- [ ] `def has_source_permission(self)`
- [ ] `def has_destination_permission(self)`
- [ ] `def has_inventory_permission(self)`
- [ ] `def can_create_picking(self)`
- [ ] `def can_write_picking(self)`
- [ ] `def can_delete_picking(self)`
- [ ] `def is_location_blocked(self, location)`

#### TASK 2.4: Actualizar models/__init__.py
- [ ] Agregar `from . import warehouse_user_permission`

---

### FASE 3: MODIFICAR MODELOS EXISTENTES 🔄
**Duración estimada:** 3-4 horas  
**Estado:** ⏸️ PENDIENTE

#### TASK 3.1: stock.warehouse
- [ ] Agregar campo `user_permission_ids = fields.One2many('warehouse.user.permission', 'warehouse_id')`
- [ ] Deprecar campo `user_ids` (Many2many) con `deprecated=True`
- [ ] Deprecar campo `restrict_location` con `deprecated=True`
- [ ] Eliminar campo `is_transit_warehouse` (ahora solo en location)
- [ ] Modificar `_onchange_restrict_location` (marcar deprecated)
- [ ] Mantener `action_open_users_view()` pero actualizar para abrir permission matrix
- [ ] Actualizar `create()` para NO auto-asignar user_ids
- [ ] Actualizar `write()` validations (eliminar check de self-removal)

#### TASK 3.2: res.users
- [ ] Agregar campo `warehouse_permission_ids = fields.One2many('warehouse.user.permission', 'user_id')`
- [ ] Deprecar `location_ids` con `deprecated=True`
- [ ] Deprecar `allowed_warehouse_ids` con `deprecated=True`
- [ ] Deprecar `restrict_location` con `deprecated=True`
- [ ] Eliminar compute `_compute_check_user` (ya no aplica)
- [ ] Eliminar cache clearing en create/write

#### TASK 3.3: stock.move
- [ ] Reescribir `_check_warehouse_transfer_permission()` completo
- [ ] Nueva lógica:
  ```python
  # 1. Skip superuser
  # 2. Skip unrestricted users
  # 3. Get source/dest warehouses
  # 4. Get user permissions for each warehouse
  # 5. Check full_control bypass
  # 6. Check view_only block
  # 7. Validate source permission (allow_as_source)
  # 8. Validate destination permission (allow_as_destination)
  # 9. Check transit locations bypass
  # 10. Check blocked locations
  # 11. Raise ValidationError if blocked
  ```
- [ ] Eliminar validación por grupos (Full/Source Only)
- [ ] Mantener validación de transit locations

#### TASK 3.4: stock.picking
- [ ] Actualizar `_onchange_location_id()` domain
- [ ] Filtrar por `user.warehouse_permission_ids.warehouse_id`
- [ ] Filtrar por `NOT IN user.warehouse_permission_ids.blocked_location_ids`
- [ ] Agregar filtro `allow_transit=True` para transit locations

#### TASK 3.5: res.config.settings
- [ ] Simplificar `_onchange_group_user_warehouse_restriction()`
- [ ] Eliminar auto-assignment a warehouses (ya no usa user_ids)
- [ ] Actualizar help text del campo
- [ ] Mantener activación de implied_group

---

### FASE 4: SEGURIDAD Y RECORD RULES 🔄
**Duración estimada:** 2-3 horas  
**Estado:** ⏸️ PENDIENTE

#### TASK 4.1: Grupos (econovo_user_warehouse_restriction_groups.xml)
- [ ] ELIMINAR grupo `group_warehouse_restriction_source_only`
- [ ] ELIMINAR grupo `group_warehouse_restriction_full`
- [ ] MANTENER grupo `user_warehouse_restriction_group_user`
- [ ] MANTENER grupo `group_warehouse_unrestricted`
- [ ] Actualizar descripciones y help texts

#### TASK 4.2: Access Rights (ir.model.access.csv)
- [ ] Crear archivo `security/ir.model.access.csv`
- [ ] Access para `warehouse.user.permission`:
  - `stock.group_stock_user`: read
  - `stock.group_stock_manager`: all
  - `base.group_system`: all

#### TASK 4.3: Record Rules (econovo_user_warehouse_restriction_security.xml)
- [ ] ELIMINAR `stock_move_rule_full_restriction`
- [ ] ELIMINAR `stock_move_rule_source_only`
- [ ] ELIMINAR `stock_move_line_rule_full_restriction`
- [ ] ELIMINAR `stock_move_line_rule_source_only`
- [ ] ACTUALIZAR `operation_type_rule_users` (usar permission_ids)
- [ ] ACTUALIZAR `stock_location_rule_users` (usar blocked_location_ids)
- [ ] ACTUALIZAR `stock_warehouse_rule_users` (usar permission_ids)
- [ ] ACTUALIZAR `stock_picking_rule_users` (usar permission_ids)
- [ ] ACTUALIZAR `stock_quant_rule_users` (usar permission_ids)
- [ ] CREAR `stock_move_rule_users` (regla única)
- [ ] CREAR `stock_move_line_rule_users` (regla única)
- [ ] Cambiar group reference a `user_warehouse_restriction_group_user`

---

### FASE 5: VISTAS Y UI 🔄
**Duración estimada:** 4-5 horas  
**Estado:** ⏸️ PENDIENTE

#### TASK 5.1: warehouse.user.permission views (NUEVO)
- [ ] Crear `views/warehouse_user_permission_views.xml`
- [ ] Form view individual (para edición detallada):
  - Header: user_id, warehouse_id
  - Group: Modos especiales (full_control, view_only)
  - Group: Warehouse permissions (Src, Dst, Inv)
  - Group: Operation permissions (Cr, Wr, Del)
  - Group: Location restrictions (blocked_location_ids, allow_transit)
  - Statusbar: active
- [ ] Tree view editable (para matriz en warehouse):
  - Columnas: user_id, full_control, view_only, allow_as_source, allow_as_destination, allow_inventory_adjustment, allow_create_picking, allow_write_picking, allow_delete_picking, allow_transit, blocked_location_ids
  - Atributo: `editable="bottom"`
  - Widget para boolean: `widget="boolean_toggle"`
  - Widget para M2M: `widget="many2many_tags"`

#### TASK 5.2: stock.warehouse form view
- [ ] Modificar `views/stock_warehouse_views.xml`
- [ ] Reemplazar campo `user_ids` con `user_permission_ids`
- [ ] Usar tree view editable in-line:
  ```xml
  <field name="user_permission_ids" nolabel="1">
      <tree editable="bottom">
          <field name="user_id"/>
          <field name="full_control" widget="boolean_toggle"/>
          <field name="view_only" widget="boolean_toggle"/>
          <field name="allow_as_source" widget="boolean_toggle"/>
          <field name="allow_as_destination" widget="boolean_toggle"/>
          <field name="allow_inventory_adjustment" widget="boolean_toggle"/>
          <field name="allow_create_picking" widget="boolean_toggle"/>
          <field name="allow_write_picking" widget="boolean_toggle"/>
          <field name="allow_delete_picking" widget="boolean_toggle"/>
          <field name="allow_transit" widget="boolean_toggle"/>
          <field name="blocked_location_ids" widget="many2many_tags"/>
      </tree>
  </field>
  ```
- [ ] Eliminar campo `restrict_location`
- [ ] Eliminar checkbox `is_transit_warehouse`
- [ ] Actualizar botón "Restrict location for User" → "Manage User Permissions"

#### TASK 5.3: res.users form view
- [ ] Modificar `views/res_users_views.xml`
- [ ] Eliminar pestaña "Restricted Location"
- [ ] Crear nueva pestaña "Warehouse Permissions":
  ```xml
  <page name="warehouse_permissions" string="Warehouse Permissions">
      <field name="warehouse_permission_ids" nolabel="1">
          <tree>
              <field name="warehouse_id"/>
              <field name="full_control" widget="boolean_toggle"/>
              <field name="view_only" widget="boolean_toggle"/>
              <field name="allow_as_source" widget="boolean_toggle"/>
              <field name="allow_as_destination" widget="boolean_toggle"/>
              <field name="allow_inventory_adjustment" widget="boolean_toggle"/>
              <button name="%(action_warehouse_user_permission_form)d" 
                      type="action" 
                      icon="fa-edit" 
                      string="Edit Details"/>
          </tree>
      </field>
  </page>
  ```

#### TASK 5.4: res.config.settings view
- [ ] Modificar `views/res_config_settings_views.xml`
- [ ] Actualizar help text de `group_user_warehouse_restriction`:
  ```
  Enable warehouse access restrictions per user.
  Users must be assigned to warehouses via permission matrix.
  Configure permissions in: Inventory > Configuration > Warehouses
  ```

---

### FASE 6: MIGRACIÓN Y HOOKS 🔄
**Duración estimada:** 3-4 horas  
**Estado:** ⏸️ PENDIENTE

#### TASK 6.1: Función de migración principal
- [ ] Crear `_migrate_to_permission_matrix(env)` en hooks.py
- [ ] Logging: Inicio de migración
- [ ] Obtener todos los warehouses con user_ids asignados
- [ ] Para cada warehouse:
  - Obtener lista de usuarios en `warehouse.user_ids`
  - Para cada usuario:
    - Verificar grupo del usuario
    - Crear registro `warehouse.user.permission` con mapeo:
      - Si `group_warehouse_unrestricted`: NO crear (bypass)
      - Si `group_warehouse_restriction_full`: `full_control=True`
      - Si `group_warehouse_restriction_source_only`: `allow_as_source=True, allow_as_destination=False`
      - Si `user_warehouse_restriction_group_user` (sin Full ni Source Only): `allow_as_source=True, allow_as_destination=True`
    - Si `warehouse.restrict_location=True`:
      - Migrar `user.location_ids` → `permission.blocked_location_ids`
- [ ] Logging: Cantidad de registros migrados
- [ ] Commit intermedio cada 100 registros

#### TASK 6.2: Cleanup de datos legacy
- [ ] Crear `_cleanup_legacy_groups(env)` en hooks.py
- [ ] Remover usuarios de `group_warehouse_restriction_source_only`
- [ ] Remover usuarios de `group_warehouse_restriction_full`
- [ ] Mantener usuarios en `user_warehouse_restriction_group_user`
- [ ] Logging: Usuarios removidos de grupos deprecated

#### TASK 6.3: Actualizar post_init_hook
- [ ] Modificar `post_init_hook(cr, registry)` en hooks.py
- [ ] Orden de ejecución:
  1. `_migrate_from_cybrosys_module(env)` (existente)
  2. `_migrate_to_permission_matrix(env)` (nueva)
  3. `_cleanup_legacy_groups(env)` (nueva)
  4. `_assign_restriction_groups(env)` (existente, modificar)
- [ ] Logging completo de todas las operaciones

#### TASK 6.4: Datos de demo (opcional)
- [ ] Crear `demo/warehouse_user_permission_demo.xml`
- [ ] Ejemplos de permisos:
  - Usuario Full Control en 1 almacén
  - Usuario con permisos granulares diferentes en 2 almacenes
  - Usuario solo lectura
  - Usuario con ubicaciones bloqueadas

---

### FASE 7: TESTING Y VALIDACIÓN 🔄
**Duración estimada:** 4-5 horas  
**Estado:** ⏸️ PENDIENTE

#### TASK 7.1: Testing de instalación
- [ ] Crear base de datos limpia Odoo 17
- [ ] Instalar módulo `stock`
- [ ] Instalar módulo `econovo_user_warehouse_restriction` v2.0
- [ ] Verificar post_init_hook ejecuta sin errores
- [ ] Verificar modelo `warehouse.user.permission` creado
- [ ] Verificar access rights aplicados
- [ ] Verificar 7 record rules activos (no 9)
- [ ] Verificar 2 grupos activos (no 4)

#### TASK 7.2: Testing de migración
- [ ] Crear base de datos con módulo v1.0 instalado
- [ ] Crear datos de prueba:
  - 3 warehouses con user_ids asignados
  - Usuarios con diferentes grupos (Full, Source Only, Base)
  - Usuarios con location_ids bloqueadas
- [ ] Actualizar a módulo v2.0
- [ ] Verificar migration hook ejecuta correctamente
- [ ] Verificar registros `warehouse.user.permission` creados
- [ ] Verificar mapeo correcto de grupos → permisos
- [ ] Verificar location_ids migrados a blocked_location_ids
- [ ] Verificar grupos deprecated limpiados

#### TASK 7.3: Testing funcional - Permisos Warehouse-level
- [ ] Crear usuario con `allow_as_source=True, allow_as_destination=False` en WH1
- [ ] Verificar puede crear: WH1 → Cliente (delivery)
- [ ] Verificar NO puede crear: Proveedor → WH1 (receipt)
- [ ] Crear usuario con `allow_inventory_adjustment=True` en WH1
- [ ] Verificar puede ajustar stock en WH1
- [ ] Verificar NO puede ajustar en WH2

#### TASK 7.4: Testing funcional - Permisos Operation-level
- [ ] Crear usuario con `allow_create_picking=True, allow_write_picking=False`
- [ ] Verificar puede crear picking draft
- [ ] Verificar NO puede validar picking (botón Validate bloqueado)
- [ ] Crear usuario con `allow_write_picking=True, allow_delete_picking=False`
- [ ] Verificar puede modificar picking
- [ ] Verificar NO puede eliminar picking

#### TASK 7.5: Testing funcional - Modos especiales
- [ ] Crear usuario con `full_control=True` en WH1
- [ ] Verificar TODOS los permisos habilitados en WH1
- [ ] Verificar NINGÚN permiso en WH2 (no asignado)
- [ ] Crear usuario con `view_only=True` en WH1
- [ ] Verificar puede VER datos en WH1
- [ ] Verificar NO puede crear/modificar/eliminar nada

#### TASK 7.6: Testing funcional - Location restrictions
- [ ] Crear usuario con `blocked_location_ids=[WH1/QC, WH1/Quarantine]`
- [ ] Verificar puede acceder WH1/Stock
- [ ] Verificar NO puede ver WH1/QC en dropdowns
- [ ] Verificar NO puede crear moves hacia WH1/Quarantine
- [ ] Crear usuario con `allow_transit=False`
- [ ] Verificar NO puede ver ubicaciones transit en dropdowns
- [ ] Crear usuario con `allow_transit=True`
- [ ] Verificar puede usar ubicaciones transit

#### TASK 7.7: Testing de Record Rules
- [ ] Verificar `stock.warehouse` filtra por permission_ids
- [ ] Verificar `stock.location` filtra por blocked_location_ids
- [ ] Verificar `stock.picking.type` filtra por warehouse permissions
- [ ] Verificar `stock.picking` filtra correctamente
- [ ] Verificar `stock.quant` filtra por warehouse + transit
- [ ] Verificar `stock.move` filtra por source O destination
- [ ] Verificar `stock.move.line` filtra correctamente

#### TASK 7.8: Testing de validaciones
- [ ] Intentar crear permission con `view_only=True` + `allow_create_picking=True`
- [ ] Verificar ValidationError
- [ ] Intentar crear 2 permissions para mismo user+warehouse
- [ ] Verificar SQL constraint error
- [ ] Verificar onchange warning: Create sin Write

---

### FASE 8: DOCUMENTACIÓN 🔄
**Duración estimada:** 2-3 horas  
**Estado:** ⏸️ PENDIENTE

#### TASK 8.1: README.md
- [ ] Actualizar descripción del módulo
- [ ] Documentar arquitectura de permission matrix
- [ ] Explicar diferencias vs v1.0 (grupos heredados)
- [ ] Guía de migración desde v1.0
- [ ] Ejemplos de configuración de permisos
- [ ] Screenshots de matriz en warehouse form

#### TASK 8.2: __manifest__.py
- [ ] Actualizar description con nueva arquitectura
- [ ] Actualizar version a `17.0.2.0.0`
- [ ] Agregar breaking changes warning
- [ ] Actualizar lista de features

#### TASK 8.3: Docstrings
- [ ] Documentar modelo `warehouse.user.permission`
- [ ] Documentar cada campo con ejemplos
- [ ] Documentar helper methods
- [ ] Documentar constraints y validaciones
- [ ] Documentar migration functions en hooks.py

#### TASK 8.4: Guía de usuario (opcional)
- [ ] Crear `docs/USER_GUIDE.md`
- [ ] Casos de uso comunes
- [ ] Cómo configurar permisos paso a paso
- [ ] Troubleshooting
- [ ] FAQs

---

### FASE 9: CLEANUP Y OPTIMIZACIÓN 🔄
**Duración estimada:** 2-3 horas  
**Estado:** ⏸️ PENDIENTE

#### TASK 9.1: Eliminar código deprecated
- [ ] Revisar TODOs en código
- [ ] Eliminar campos marcados `deprecated=True` (después de period de gracia)
- [ ] Eliminar funciones legacy no utilizadas
- [ ] Eliminar imports innecesarios

#### TASK 9.2: Optimización de queries
- [ ] Agregar índices en `warehouse.user.permission`:
  - `CREATE INDEX ON warehouse_user_permission(user_id, warehouse_id)`
- [ ] Review de Record Rules (dominios eficientes)
- [ ] Cache de permisos (si aplica)

#### TASK 9.3: Code review
- [ ] Verificar naming conventions Odoo 17
- [ ] Verificar PEP8 compliance
- [ ] Verificar XML formatting
- [ ] Eliminar código comentado
- [ ] Verificar strings en inglés (no español hardcoded)

---

### FASE 10: DEPLOY Y COMMIT 🔄
**Duración estimada:** 1 hora  
**Estado:** ⏸️ PENDIENTE

#### TASK 10.1: Git commits
- [ ] Commit message estándar Odoo:
  ```
  [REF] econovo_user_warehouse_restriction: Refactor to permission matrix
  
  Replace group-based inheritance (3 levels) with granular permission
  matrix per user/warehouse.
  
  Breaking changes:
  - Removed groups: group_warehouse_restriction_source_only, group_warehouse_restriction_full
  - New model: warehouse.user.permission
  - Deprecated fields: warehouse.user_ids, user.location_ids
  
  Migration hook included to preserve existing permissions.
  ```
- [ ] Tag version: `git tag 17.0.2.0.0`

#### TASK 10.2: Testing en servidor staging
- [ ] Deploy en servidor de pruebas
- [ ] Actualizar módulo con `-u econovo_user_warehouse_restriction`
- [ ] Verificar migración en datos reales
- [ ] Verificar permisos funcionan correctamente
- [ ] User acceptance testing

#### TASK 10.3: Deploy producción (cuando esté aprobado)
- [ ] Backup base de datos
- [ ] Deploy en producción
- [ ] Actualizar módulo
- [ ] Verificar logs de migración
- [ ] Monitorear errores

---

## 📊 MATRIZ DE RIESGOS

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Pérdida de permisos durante migración | Media | Alto | Hook de migración exhaustivo + backup |
| Record Rules ineficientes (performance) | Baja | Medio | Índices en BD + testing con datos reales |
| Usuarios quedan bloqueados post-update | Media | Alto | Auto-assign admins + validation en hook |
| Inconsistencias lógicas en permisos | Media | Medio | Constraints Python + validaciones |
| Breaking changes afectan integraciones | Alta | Alto | Documentación + deprecation warnings |

---

## 🎯 CRITERIOS DE ACEPTACIÓN

### Funcionales
- [x] Usuario puede tener permisos DIFERENTES en cada almacén
- [ ] Full Control funciona POR ALMACÉN (no global)
- [ ] View Only bloquea todas las operaciones de escritura
- [ ] Blocked Locations funcionan como blacklist
- [ ] Transit locations bypass restrictions
- [ ] Record Rules filtran correctamente según permission matrix
- [ ] Python constraints validan Src/Dst según permisos

### Técnicos
- [ ] 0 errores en instalación limpia
- [ ] 0 errores en migración desde v1.0
- [ ] 0 warnings en logs (excepto deprecation)
- [ ] Performance: Queries < 100ms (warehouse con 1000 users)
- [ ] Cobertura de tests: Funcionales (casos críticos cubiertos)

### UX
- [ ] Matriz de permisos editable in-line en warehouse form
- [ ] Columnas con checkboxes toggle (fácil activar/desactivar)
- [ ] Help texts claros en cada columna
- [ ] Warnings cuando configuración es incompleta (Cr sin Wr)
- [ ] Navegación rápida: Warehouse → Users → Permissions

---

## 📝 NOTAS DE IMPLEMENTACIÓN

### Decisiones Arquitectónicas

1. **¿Por qué eliminar grupos heredados?**
   - Herencia causa conflictos (Full hereda Source Only → ambas reglas aplican con OR)
   - Inflexible: Usuario tiene MISMO nivel en TODOS sus almacenes
   - Difícil de mantener: 3 niveles de herencia

2. **¿Por qué One2many en lugar de Many2many?**
   - Granularidad: Cada registro permission tiene flags independientes
   - Auditoría: Cada permiso es un registro con create_date, write_uid
   - Escalabilidad: Más fácil agregar nuevos campos de permiso

3. **¿Por qué mantener transit_location en stock.location?**
   - Es propiedad de la UBICACIÓN, no del usuario
   - Todas las ubicaciones transit deben ser accesibles (por defecto)
   - Columna allow_transit en permission permite RESTRINGIR acceso (override)

4. **¿Por qué deprecar en lugar de eliminar campos legacy?**
   - Compatibilidad: Módulos externos pueden referenciar warehouse.user_ids
   - Migración suave: Period de gracia de 1-2 versiones
   - Warnings: Ayuda a developers a actualizar código

### Pendientes de Decisión

- [ ] **DECISIÓN REQUERIDA:** ¿allow_transit debe ser True por defecto o False?
  - Opción A (True): Usuarios pueden usar transit SALVO que explícitamente se bloquee
  - Opción B (False): Usuarios NO pueden usar transit SALVO que explícitamente se permita
  - **Recomendación:** True (menos restrictivo, facilita workflows)

- [ ] **DECISIÓN REQUERIDA:** ¿Eliminar completamente grupos Source Only y Full o mantenerlos deprecated?
  - Opción A: Eliminar completamente (clean break)
  - Opción B: Mantener deprecated por 1 versión (smoother migration)
  - **Recomendación:** Opción B

---

## 🔄 CONTROL DE CAMBIOS

| Fecha | Versión | Cambios | Autor |
|-------|---------|---------|-------|
| 2025-11-22 | 1.0 | Documento inicial de planificación | Jose D. Leonett |

---

## ✅ CHECKLIST DE APROBACIÓN

Antes de proceder con implementación, confirmar:

- [ ] Arquitectura de permission matrix aprobada
- [ ] 10 columnas de permisos validadas
- [ ] Lógica de Full Control POR ALMACÉN confirmada
- [ ] Plan de migración revisado
- [ ] Riesgos identificados y aceptados
- [ ] Timeline y estimaciones aceptables
- [ ] Recursos disponibles para testing

---

**ESTADO ACTUAL:** 📋 **ESPERANDO APROBACIÓN DEL USUARIO**

Una vez aprobado, proceder con **FASE 2: MODELO DE DATOS** (TASK 2.1).
