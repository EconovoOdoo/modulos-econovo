# Econovo - Stock Barcode Workcenter Display

## Overview

This module displays the assigned workcenter (Centro de trabajo) in the Barcode
application's picking detail view.

## Features

- Shows the workcenter name in a subtle info bar below the picking reference
  in the header area of the barcode app
- Only visible when the picking has an assigned workcenter
- If no workcenter is assigned, nothing is shown

## Requirements

- The Studio field `x_studio_workcenter_id` must exist on `stock.picking`
- Module `stock_barcode` (Enterprise) must be installed
- Module `mrp` must be installed

## Configuration

No additional configuration needed. Install the module and the workcenter
will automatically appear in the barcode picking view when assigned.
