# Instructivo: Cómo Reubicar Productos con la App de Códigos de Barras

**Versión:** 3.0 | **Fecha:** Diciembre 2025 | **Dirigido a:** Operarios de almacén

---

## 🔄 Diagrama de Flujo

```mermaid
flowchart TD
    Start([🎯 Inicio]) --> ScanProduct[📱 App Códigos de Barras<br/>📷 Escanear producto y marcar casilla]
    
    ScanProduct --> DecideQty{¿Reubicar TODO?}
    
    DecideQty -->|✅ SÍ, TODO| ClickRelocate[🔘 Botón 'Reubicar']
    DecideQty -->|❌ NO, Parcial| ClickActions[⚙️ Acciones → Mover Stock<br/>🪟 Ingresar CANTIDAD]
    
    ClickRelocate --> CheckDest{¿Ubicación<br/>existe?}
    ClickActions --> CheckDest
    
    CheckDest -->|✅ SÍ| SelectDest[📍 Seleccionar ubicación]
    CheckDest -->|❌ NO| CreateLoc[🆕 Nueva pestaña → Crear ubicación<br/>Inventario → Config → Ubicaciones]
    CreateLoc --> SelectDest
    
    SelectDest --> Confirm[✅ Confirmar/Aplicar]
    
    Confirm --> CreateRule[🎯 Acciones → Crear Regla]
    
    CreateRule --> HasRule{¿Ya tiene<br/>regla?}
    HasRule -->|✅ SÍ| CheckReplace[☑️ Marcar 'Reemplazar<br/>reglas existentes']
    HasRule -->|❌ NO| Create
    CheckReplace --> Create[✅ Crear]
    
    Create --> End([✅ Listo])
    
    style Start fill:#e1f5e1
    style End fill:#e1f5e1
    style CreateRule fill:#fffacd
```

---

## 📋 PASOS SIMPLIFICADOS

### 1️⃣ Escanear Producto
- Abrir **App Códigos de Barras** (menú principal)
- 📷 **Escanear** el producto y **marcar su casilla** ☑️

### 2️⃣ Elegir Tipo de Reubicación

| ✅ TODO el stock | ❌ PARTE del stock |
|------------------|---------------------|
| 🔘 Clic en **"Reubicar"** | ⚙️ **Acciones** → **"Mover Stock"**<br/>🔢 Ingresar **cantidad** en ventana emergente |

### 3️⃣ Ubicación Destino

| ✅ La ubicación EXISTE | ❌ La ubicación NO EXISTE |
|------------------------|---------------------------|
| 📍 Selecciónela directamente | 🆕 Nueva pestaña (Ctrl+T)<br/>📂 **Inventario → Configuración → Ubicaciones → Crear**<br/>💾 Guardar → ⬅️ Volver |

### 4️⃣ Confirmar
- ✅ Clic en **"Confirmar"** o **"Aplicar"**

### 5️⃣ Crear Regla de Almacenamiento
- ⚙️ **Acciones** → **"Crear Regla de Almacenamiento"**

| ✅ Ya tiene regla | ❌ NO tiene regla |
|-------------------|-------------------|
| ☑️ Marcar **"Reemplazar reglas existentes"**<br/>✅ Clic en **"Crear"** | ✅ Clic en **"Crear"** |

---

## 📊 Tabla Resumen

| Paso | TODO el stock | PARTE del stock |
|------|---------------|-----------------|
| **1** | Escanear y marcar | Escanear y marcar |
| **2** | Botón "Reubicar" | Acciones → Mover Stock + Cantidad |
| **3** | Seleccionar destino | Seleccionar destino |
| **4** | Aplicar | Confirmar |
| **5** | Crear regla | Crear regla |

---

## ⚠️ Importante

- **Siempre crear la regla** después de reubicar
- **Si la ubicación no existe:** Créela en nueva pestaña sin cerrar la reubicación
- **Use el escáner** para evitar errores

---

**Creado por:** Jose D. Leonett | **GitHub:** github.com/josedleonett  
**GitHub:** https://github.com/josedleonett
