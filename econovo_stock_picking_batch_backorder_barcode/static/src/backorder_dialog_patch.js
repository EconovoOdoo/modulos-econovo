/** @odoo-module **/

import { BackorderDialog } from "@stock_barcode/components/backorder_dialog";
import BarcodeModel from "@stock_barcode/models/barcode_model";
import BarcodePickingModel from "@stock_barcode/models/barcode_picking_model";
import { backorderBatchState } from "./backorder_batch_state";
import { patch } from "@web/core/utils/patch";
import { useState } from "@odoo/owl";

patch(BarcodePickingModel.prototype, {
    async validate() {
        backorderBatchState.show = this.config.create_backorder === "ask" && Boolean(
            this.resModel === "stock.picking.batch" || this.record.batch_id
        );
        backorderBatchState.create =
            backorderBatchState.show && Boolean(this.config.create_backorder_batch);
        return super.validate(...arguments);
    },
});

patch(BarcodeModel.prototype, {
    async validate() {
        // The dialog is already closed when the request is sent, so the choice
        // is read here, right before the validation call.
        if (backorderBatchState.show) {
            this.validateContext = {
                ...this.validateContext,
                econovo_create_backorder_batch: backorderBatchState.create,
            };
            backorderBatchState.show = false;
        }
        return super.validate(...arguments);
    },
});

patch(BackorderDialog.prototype, {
    setup() {
        super.setup();
        this.backorderBatch = useState(backorderBatchState);
    },

    toggleBackorderBatch(ev) {
        backorderBatchState.create = ev.target.checked;
    },
});
