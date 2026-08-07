/** @odoo-module **/

import BarcodePickingBatchModel from '@stock_barcode_picking_batch/models/barcode_picking_batch_model';
import { patch } from "@web/core/utils/patch";

patch(BarcodePickingBatchModel.prototype, {
    _createLinesState() {
        const lines = super._createLinesState(...arguments);
        for (const line of lines) {
            // A batch mixes lines from different transfers: overrides the
            // single-transfer workcenter (set by the base patch) with the
            // one of THIS line's own origin transfer, now that `picking_id`
            // has been resolved into a full record above.
            const workcenterId = line.picking_id && line.picking_id.workcenter_id;
            line.workcenter_id = this._econovoGetCachedRecord('mrp.workcenter', workcenterId);
        }
        return lines;
    },
});

