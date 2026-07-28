/** @odoo-module **/

import { registry } from "@web/core/registry";
import { SignatureDialog } from "@web/core/signature/signature_dialog";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

import { Component } from "@odoo/owl";

/**
 * Extends the native "signature" widget (web.SignatureWidget) to also
 * capture the typed signer name into a separate Char field (e.g.
 * stock.picking.signed_by), so it can be printed alongside the signature
 * image. Unlike the native widget, the name input is never hidden
 * (noInputName: false), so the signer can type/edit their name even when
 * no full_name prefill is configured.
 */
export class SignatureSignerWidget extends Component {
    static template = "web.SignatureWidget";
    static props = {
        ...standardWidgetProps,
        fullName: { type: String, optional: true },
        highlight: { type: Boolean, optional: true },
        string: { type: String },
        signatureField: { type: String, optional: true },
        signedByField: { type: String, optional: true },
    };

    setup() {
        this.dialogService = useService("dialog");
        this.orm = useService("orm");
    }

    onClickSignature() {
        const nameAndSignatureProps = {
            mode: "draw",
            displaySignatureRatio: 3,
            signatureType: "signature",
            noInputName: false,
        };
        const { fullName, record } = this.props;
        let defaultName = "";
        if (fullName) {
            let signName;
            const fullNameData = record.data[fullName];
            if (record.fields[fullName].type === "many2one") {
                signName = fullNameData && fullNameData[1];
            } else {
                signName = fullNameData;
            }
            defaultName = signName === "" ? undefined : signName;
        }

        nameAndSignatureProps.defaultFont = this.props.defaultFont;

        const dialogProps = {
            defaultName,
            nameAndSignatureProps,
            uploadSignature: (data) => this.uploadSignature(data),
        };
        this.dialogService.add(SignatureDialog, dialogProps);
    }

    async uploadSignature({ name, signatureImage }) {
        const { model, resModel, resId } = this.props.record;
        const vals = {
            [this.props.signatureField]: signatureImage[1],
        };
        if (this.props.signedByField && name) {
            vals[this.props.signedByField] = name;
        }
        await this.orm.write(resModel, [resId], vals);
        await this.props.record.load();
        model.notify();
    }
}

export const signatureSignerWidget = {
    component: SignatureSignerWidget,
    extractProps: ({ attrs }) => {
        const { full_name: fullName, highlight, signature_field, signed_by_field, string } = attrs;
        return {
            fullName,
            highlight: !!highlight,
            string,
            signatureField: signature_field || "signature",
            signedByField: signed_by_field || "signed_by",
        };
    },
};

registry.category("view_widgets").add("signature_signer", signatureSignerWidget);
