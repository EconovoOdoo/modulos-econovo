# Econovo Stock Picking Split by Count

Adds a **"Split by Count"** mode to the picking split wizard provided by the OCA
module `stock_split_picking`, mirroring the Manufacturing Order split wizard
(`mrp.production.split`, menu *Manufacturing > Operations*).

## Usage

1. Open a single confirmed transfer (`stock.picking`) that is not yet done or
   cancelled.
2. Run the **Split** action (`stock_split_picking.action_stock_split_picking`).
3. Choose the mode **Split by Count**.
4. Set **Split Into #** (how many resulting transfers). The wizard proposes an
   even distribution of every product's demand across that many transfers
   (last one absorbs the rounding remainder).
5. Optionally edit:
   - The quantity of each product for each resulting transfer (must still add
     up to the original demand per product).
   - The responsible user and scheduled date for each resulting transfer.
6. Click **Split**. The original transfer is kept for split #1 and
   `Split Into # - 1` new backorder transfers are created for the rest,
   reusing the same backorder mechanism as the OCA module's "Quantities" mode.

## Notes / limitations

- Only a single transfer can be split at a time in this mode (unlike the
  "Quantities"/"One picking per move"/"Selection" modes, which accept a
  multi-record selection).
- The transfer must be confirmed and not `done`/`cancel`.
- Only moves that are not `done`/`cancel` are considered.
