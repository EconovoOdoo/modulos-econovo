/** @odoo-module **/

import { Component } from "@odoo/owl";
import LineComponent from "@stock_barcode/components/line";
import GroupedLineComponent from "@stock_barcode/components/grouped_line";

export class KitSublineComponent extends Component {
    static template = "econovo_barcode_kit.KitSublineComponent";
    static components = { LineComponent, GroupedLineComponent };
    static props = {
        line: Object,
        displayUOM: { type: Boolean, optional: true },
        editLine: { type: Function, optional: true },
    };
    
    get isGrouped() {
        return this.props.line.lines && this.props.line.lines.length > 0;
    }
}
