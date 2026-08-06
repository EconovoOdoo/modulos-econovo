# Econovo - Stock Barcode Workcenter Display

## Overview

This module displays the assigned workcenter (Centro de trabajo) in the Barcode
application's picking detail view, and the production context (Production
Plan + workcenter) of each line when viewing a Batch Transfer.

## Features

- Shows the workcenter name in a subtle info bar below the picking reference
  in the header area of the barcode app (single transfer view)
- Only visible when the picking has an assigned workcenter
- If no workcenter is assigned, nothing is shown
- In a Batch Transfer, since lines can belong to different transfers, each
  line also shows its own transfer's Production Plan and workcenter (below the
  origin transfer reference, above the destination location), each hidden
  independently when not set

## Requirements

- The Studio field `x_studio_workcenter_id` must exist on `stock.picking`
- Module `stock_barcode` (Enterprise) must be installed
- Module `stock_barcode_picking_batch` (Enterprise) must be installed
- Module `mrp` must be installed
- Module `econovo_mrp_component_lines` must be installed (provides
  `stock.move.production_plan_id`)

## Configuration

No additional configuration needed. Install the module and the workcenter
will automatically appear in the barcode picking view when assigned.

