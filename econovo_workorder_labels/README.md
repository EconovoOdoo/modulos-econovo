# Etiquetas para Órdenes de Trabajo - Econovo

## ¿Qué hace este módulo?

Este módulo te permite **imprimir etiquetas** para las órdenes de trabajo directamente desde Odoo. Las etiquetas son perfectas para el área de producción ya que muestran toda la información importante que los operarios necesitan conocer sobre cada tarea.

## ¿Para qué sirve?

🏭 **En el área de producción**: Los operarios pueden escanear códigos de barras y ver rápidamente qué están fabricando
📋 **Seguimiento de procesos**: Cada etiqueta muestra qué proceso viene antes y después
📊 **Control de calidad**: Información clara sobre cantidades y especificaciones
👥 **Gestión de personal**: Saber quién trabajó en cada operación

## ¿Qué información contiene cada etiqueta?

Cada etiqueta impresa incluye:

### 📦 **Información del Producto**
- Nombre y código del producto que se está fabricando
- Código de barras para escanear fácilmente

### 🔄 **Flujo de Trabajo**
- **Proceso anterior**: Qué operación debe completarse antes
- **Proceso actual**: La operación que se está realizando ahora
- **Proceso siguiente**: Qué operación viene después

### 📋 **Detalles de Producción**
- Plan de producción asignado
- Orden de fabricación principal y órdenes relacionadas
- Cantidades: cuánto se ha producido y cuánto falta
- Número de serie o lote (si aplica)

### 📅 **Información de Tiempo**
- Cuándo empezó y terminó la operación
- Fecha y hora de impresión de la etiqueta

### 👤 **Responsable**
- Quién fue la última persona que trabajó en esta operación
- Si nadie ha trabajado aún, muestra quién imprimió la etiqueta

### 🏢 **Identificación**
- Logo de la empresa
- Código de barras de la orden de fabricación para seguimiento

## ¿Cómo usar el módulo?

### Imprimir una etiqueta

1. Ve a **Fabricación** → **Órdenes de Trabajo**
2. Abre la orden de trabajo que necesitas
3. Haz clic en el botón **"Imprimir Etiqueta de la Operación"**
4. La etiqueta se genera automáticamente y está lista para imprimir

### Tamaño de las etiquetas

Las etiquetas están diseñadas para impresoras de etiquetas estándar:
- **Tamaño**: 100mm x 70mm
- **Formato**: Listo para impresoras de etiquetas adhesivas
- **Calidad**: Diseño claro y fácil de leer

## Instalación

### ¿Quién puede instalar esto?

Este módulo debe ser instalado por el **administrador del sistema** o la **persona encargada de IT**. 

### Pasos para la instalación

1. El administrador coloca el módulo en el servidor de Odoo
2. Actualiza la lista de aplicaciones
3. Busca "Etiquetas para Órdenes de Trabajo" y lo instala
4. ¡Listo! El botón de impresión aparecerá automáticamente

## Beneficios para tu empresa

✅ **Menos errores**: La información clara previene confusiones en producción
✅ **Mayor eficiencia**: Los operarios no pierden tiempo buscando información
✅ **Mejor trazabilidad**: Cada etiqueta incluye códigos de barras para seguimiento
✅ **Control de calidad**: Información detallada sobre cantidades y especificaciones
✅ **Comunicación clara**: El flujo de trabajo es visible para todos

## Preguntas Frecuentes

### ¿Funciona con cualquier impresora?
Sí, funciona con impresoras normales y con impresoras de etiquetas. El tamaño está optimizado para etiquetas adhesivas de 100x70mm.

### ¿Puedo personalizar la información?
El módulo está diseñado específicamente para Econovo, pero un desarrollador puede modificar qué información se muestra.

### ¿Se puede imprimir varias etiquetas a la vez?
Sí, puedes seleccionar múltiples órdenes de trabajo e imprimir todas sus etiquetas de una vez.

### ¿Funciona sin internet?
Sí, una vez instalado, funciona completamente dentro de tu sistema Odoo local.

## Soporte y Contacto

**Desarrollado por**: Jose D. Leonett
**Sitio web**: [https://github.com/josedleonett](https://github.com/josedleonett)
**Licencia**: AGPL-3 (Software libre)

---

*Este módulo ha sido desarrollado específicamente para optimizar los procesos de producción de Econovo, mejorando la comunicación y eficiencia en el área de manufactura.*