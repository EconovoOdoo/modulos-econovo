# econovo_fsm_worksheet

Implements the **REG-SVT-04 — Orden de Trabajo y Servicio Técnico** for the
Field Service module.

## Features

- Adds an **Equipo (N/S)** (`lot_id`) field to FSM tasks so the technician can
  link the service visit to the physical equipment serial number.
- Creates the **"Orden de Trabajo SVT-04"** worksheet template with operational
  custom fields:
  - Horómetro actual, Nro Remito, OC Cliente, Nro Interno, Nro Factura, Obs. Interno
  - Tipo de servicio (50/250 HS, 500 HS, 750 HS, 1000 HS, Otro)
  - Tipo de falla (Eléctrico, Mecánico, Hidráulico, Otro)
  - Equipo Operativo (SI/NO), Próxima Visita (hs)
  - Observaciones para el cliente, DNI Firmante
- Provides a **custom PDF report** ("Orden de Trabajo SVT-04") that replicates the
  REG-SVT-04 form layout:
  - Company logo + document code header
  - Equipment data from `stock.lot` (marca, modelo, nro_chasis)
  - **Timesheets as work description** (native `timesheet_ids`)
  - **Materials from the linked sale order** (SOLs excluding the service line)
  - Checkbox-style rendering for tipo_servicio and tipo_falla
  - Signature block with DNI
- A stored related `x_lot_id` on the worksheet model enables group-by on
  equipment in the Analysis (pivot/graph) view.

## Dependencies

`industry_fsm`, `industry_fsm_report`, `industry_fsm_sale`, `stock`,
`worksheet`, `gg_lot_data`

## Notes

- Materials filter: excludes `task.sale_line_id` (the main service billing line)
  and shows all other SOLs on the linked SO as materials/parts used.
- `x_obs_interno` field visibility in the PDF is deferred (§8.D3 of the plan).
- The standard "Field Service Report" also works for these tasks — the auto-generated
  worksheet QWeb is regenerated from the custom form view during `post_init_hook`.
