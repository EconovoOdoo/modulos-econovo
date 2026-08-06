/** @odoo-module **/

import BarcodePickingBatchModel from '@stock_barcode_picking_batch/models/barcode_picking_batch_model';
import { patch } from "@web/core/utils/patch";

patch(BarcodePickingBatchModel.prototype, {
    _createLinesState() {
        const lines = super._createLinesState(...arguments);
        for (const line of lines) {
            line.production_plan_id = this._econovoGetCachedRecord('mrp.plan', line.production_plan_id);
            const workcenterId = line.picking_id && line.picking_id.x_studio_workcenter_id;
            line.workcenter_id = this._econovoGetCachedRecord('mrp.workcenter', workcenterId);
        }
        return lines;
    },

    /**
     * `cache.getRecord` can throw if the id isn't (yet) present in the cache.
     */
    _econovoGetCachedRecord(model, id) {
        if (!id) {
            return false;
        }
        try {
            return this.cache.getRecord(model, id);
        } catch {
            return false;
        }
    },
});
