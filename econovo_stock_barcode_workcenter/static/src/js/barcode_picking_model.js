/** @odoo-module **/

import BarcodePickingModel from '@stock_barcode/models/barcode_picking_model';
import { patch } from "@web/core/utils/patch";

patch(BarcodePickingModel.prototype, {
    _getModelRecord() {
        const record = super._getModelRecord(...arguments);
        if (record.x_studio_workcenter_id) {
            try {
                record.x_studio_workcenter_id = this.cache.getRecord(
                    'mrp.workcenter', record.x_studio_workcenter_id
                );
            } catch {
                // Field or record not available, keep the raw ID.
            }
        }
        return record;
    },
});
