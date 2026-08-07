# Econovo - Stock Barcode Workcenter Display

## Overview

This module displays the assigned workcenter (Centro de trabajo) in the Barcode
application's picking detail view, and the production context (Production
Plan + workcenter) of each line, on both regular transfers and Batch
Transfers.

## Features

- Shows the workcenter name in a subtle info bar below the picking reference
  in the header area of the barcode app (single transfer view)
- Only visible when the picking has an assigned workcenter
- If no workcenter is assigned, nothing is shown
- Each line also shows its own transfer's Production Plan and workcenter
  (below the origin transfer reference, above the destination location),
  each hidden independently when not set. In a Batch Transfer, lines can
  belong to different transfers and show different values accordingly.

## Requirements

- Module `stock_barcode` (Enterprise) must be installed
- Module `stock_barcode_picking_batch` (Enterprise) must be installed
- Module `mrp` must be installed
- Module `econovo_mrp_component_lines` must be installed (provides
  `_get_supply_production`)
- Module `econovo_stock_picking_production_info` must be installed (provides
  `stock.picking.workcenter_id` / `production_plan_id`)

## Configuration


No additional configuration needed. Install the module and the workcenter
will automatically appear in the barcode picking view when assigned.

