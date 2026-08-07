/** @odoo-module **/

import BarcodePickingModel from '@stock_barcode/models/barcode_picking_model';
import { patch } from "@web/core/utils/patch";

patch(BarcodePickingModel.prototype, {
    _getModelRecord() {
        const record = super._getModelRecord(...arguments);
        if (record.workcenter_id) {
            try {
                record.workcenter_id = this.cache.getRecord(
                    'mrp.workcenter', record.workcenter_id
                );
            } catch {
                // Field or record not available, keep the raw ID.
            }
        }
        return record;
    },
});
