/** @odoo-module **/

import MainComponent from '@stock_barcode/components/main';
import { SignatureDialog } from "@web/core/signature/signature_dialog";
import { patch } from "@web/core/utils/patch";

/**
 * Patch the Barcode app MainComponent to add a "Sign" button next to the
 * information/scanner/settings icons in the top navigation bar. Reuses the
 * native web SignatureDialog, the same component used by stock.picking's
 * own "Sign" widget in the classic form view.
 */
patch(MainComponent.prototype, {
    onClickSign() {
        const dialogProps = {
            nameAndSignatureProps: {
                mode: "draw",
                displaySignatureRatio: 3,
                signatureType: "signature",
            },
            uploadSignature: ({ name, signatureImage }) =>
                this.env.model.uploadSignature(name, signatureImage[1]),
        };
        this.dialog.add(SignatureDialog, dialogProps);
    },
});
