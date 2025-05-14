# Econovo Workorder Labels

## Descripción

El módulo `econovo_workorder_labels` está diseñado para facilitar la impresión de etiquetas personalizadas para órdenes de trabajo en Odoo. Estas etiquetas tienen un formato de 100x70mm específicamente adaptado a los procesos de producción de Econovo, mostrando información esencial sobre cada orden de trabajo y haciendo más fácil la gestión y seguimiento de los procesos productivos.

## Características

- Impresión de etiquetas para órdenes de trabajo con la siguiente información:
  - Código de barras del producto (Code128)
  - Código y nombre del producto
  - Proceso anterior (workorder bloqueante)
  - Proceso actual (workorder actual)
  - Proceso siguiente (workorder dependiente)
  - Orden de fabricación actual y órdenes padre (si existen)
  - Serie/Lote del producto
  - Cantidad producida y a producir
  - Fechas de inicio y fin de la operación
  - Logo de la empresa y fecha/hora de impresión

## Formato de Etiqueta

- Tamaño personalizado: 100x70mm
- Diseño optimizado para claridad y visibilidad
- Incluye código de barras del producto
- Muestra el flujo de trabajo con indicadores visuales para procesos anteriores y siguientes

## Instalación

Para instalar el módulo `econovo_workorder_labels`, sigue estos pasos:

1. Coloca la carpeta del módulo en tu directorio de addons de Odoo.
2. Actualiza la lista de aplicaciones en Odoo.
3. Busca "Econovo Workorder Labels" en el menú de aplicaciones.
4. Haz clic en el botón de instalar.

## Uso

Una vez instalado, el módulo añade un botón "Imprimir Etiqueta de la Operación" en la vista de formulario de órdenes de trabajo. Los usuarios pueden generar e imprimir etiquetas directamente desde la interfaz de Odoo haciendo clic en este botón.

## Dependencias

Este módulo depende de los siguientes módulos de Odoo:
- `mrp` (Manufactura)

## Autor

Jose D. Leonett

## Licencia

AGPL-3

## Sitio Web

[http://josedleonett.github.com](http://josedleonett.github.com)