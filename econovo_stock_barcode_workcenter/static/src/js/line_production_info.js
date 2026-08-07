/** @odoo-module **/

import BarcodePickingModel from '@stock_barcode/models/barcode_picking_model';
import { patch } from "@web/core/utils/patch";

patch(BarcodePickingModel.prototype, {
    _createLinesState() {
        const lines = super._createLinesState(...arguments);
        for (const line of lines) {
            line.production_plan_id = this._econovoGetCachedRecord('mrp.plan', line.production_plan_id);
            // Single transfer: every line shares the same workcenter as the
            // picking being viewed. In a Batch Transfer, this is overridden
            // per line by its own patch once `picking_id` is resolved.
            line.workcenter_id = this._econovoGetCachedRecord('mrp.workcenter', this.record.workcenter_id);
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
