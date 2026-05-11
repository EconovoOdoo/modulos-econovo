/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import {
    buildCategoryTree,
    enrichCategoryTree,
} from "@econovo_mrp_bom_cost_summary/utils/bom_cost_summary_utils";
import { getStateDecorator } from "@mrp/components/mo_overview_line/mo_overview_colors";

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/**
 * Inserts or merges a single MO component into the category map.
 *
 * Builds two parallel structures on each product entry:
 *
 *  - mo_replenishments[]: one entry per replenishment whose model is
 *    'mrp.production' (sub-MOs).  Each entry carries the sub-MO name,
 *    state badge data, and the quantity consumed by THAT sub-MO so a
 *    dedicated usage row can be rendered underneath it.
 *
 *  - usages[]: aggregated usages from replenishments that are NOT
 *    sub-MOs (stock, purchase orders, "to_order" lines) plus the
 *    top-level component move itself when there are no sub-MO
 *    replenishments for it.  These render as plain usage rows.
 *
 * @param {Object} categoryMap    - Accumulator keyed by categ_id
 * @param {Object} comp           - Component summary dict (compWrapper.summary)
 * @param {Array}  replenishments - compWrapper.replenishments array
 * @param {number} moCost         - mo_cost (estimated / theoretical)
 * @param {number} realCost       - real_cost (actual consumed)
 * @param {string} parentName     - Name of the finished product (the MO product)
 * @param {number} parentProductId- product.product ID of the finished product
 * @param {number} catId          - Category ID (read from wrapper)
 * @param {string} catName        - Category name
 * @param {Array}  catAncestors   - [{id, name}] list from root to leaf
 */
function _addMoComponentEntry(categoryMap, comp, replenishments, moCost, realCost, parentName, parentProductId, catId, catName, catAncestors) {
    catId = catId !== undefined ? catId : (comp.categ_id || 0);
    catName = catName !== undefined ? catName : (comp.categ_name || _t("Uncategorized"));
    catAncestors = catAncestors !== undefined ? catAncestors : (comp.categ_ancestors || [{ id: catId, name: catName }]);

    if (!categoryMap[catId]) {
        categoryMap[catId] = {
            id: catId,
            name: catName,
            total: 0,
            prod_cost_total: 0,
            products: {},
            ancestors: catAncestors,
        };
    }
    const cat = categoryMap[catId];
    cat.total += moCost;
    cat.prod_cost_total += realCost;

    const prodId = comp.product_id;
    if (!cat.products[prodId]) {
        cat.products[prodId] = {
            product_id: prodId,
            name: comp.name,
            link_id: prodId,
            link_model: "product.product",
            total: 0,
            prod_cost_total: 0,
            // Sub-MO replenishments: one entry per mrp.production replenishment.
            // Each carries its own usage row data (name, state badge, quantity).
            mo_replenishments: [],
            // Non-sub-MO usages: stock draws, purchase orders.
            usages: [],
            // Components flagged as "to_order" (need replenishment): one entry
            // per parent MO, shown with a "Reabastecer" button in the table.
            to_order_replenishments: [],
            quantity_available: comp.quantity_free !== undefined ? comp.quantity_free : false,
            quantity_on_hand: comp.quantity_on_hand !== undefined ? comp.quantity_on_hand : false,
            quantity_reserved: comp.quantity_reserved !== undefined ? comp.quantity_reserved : false,
            receipt: comp.receipt || null,
            availability_state: false,
            availability_display: "",
            in_transit_replenishments: [],
        };
    }
    const product = cat.products[prodId];
    product.total += moCost;
    product.prod_cost_total += realCost;

    // ---- Partition replenishments into sub-MOs vs. in_transit vs. standard usages ----
    const reps = replenishments || [];
    const subMoReps = reps.filter((r) => r.summary && r.summary.model === "mrp.production");
    const inTransitReps = reps.filter((r) => r.summary && r.summary.model === "in_transit");
    const otherReps = reps.filter(
        (r) => !r.summary || (r.summary.model !== "mrp.production" && r.summary.model !== "in_transit")
    );

    // Register sub-MO replenishments (each becomes a dedicated child row with badge).
    for (const rep of subMoReps) {
        const s = rep.summary;
        // Avoid duplicates when the same product appears in multiple compWrappers
        // (shouldn't happen for MO components, but guard anyway).
        const alreadyExists = product.mo_replenishments.find((r) => r.mo_id === s.id);
        if (!alreadyExists) {
            product.mo_replenishments.push({
                mo_id: s.id,
                name: s.name || _t("Manufacturing Order"),
                state: s.state || "",
                formatted_state: s.formatted_state || s.state || "",
                state_class: getStateDecorator("mrp.production", s.state || ""),
                // Usage row data shown directly under this sub-MO row.
                usage_quantity: s.quantity || 0,
                usage_uom_name: comp.uom_name || "",
                parent_name: parentName,
                parent_product_id: parentProductId,
            });
        }
    }

    // Register in_transit replenishments (goods already shipped, not yet received).
    for (const rep of inTransitReps) {
        const s = rep.summary;
        product.in_transit_replenishments.push({
            product_id: prodId,
            quantity: s.quantity || 0,
            uom_name: s.uom_name || "",
            receipt: s.receipt || null,
            parent_name: parentName,
            parent_product_id: parentProductId,
        });
    }

    // If the component itself is flagged as "to_order" (needs procurement),
    // route it to to_order_replenishments[] so a dedicated Reabastecer row
    // is shown instead of a plain usage row.
    const isToOrder = comp.model === 'to_order' || comp.state === 'to_order';
    if (isToOrder) {
        const existingToOrder = product.to_order_replenishments.find(
            (r) => r.parent_product_id === parentProductId
        );
        if (existingToOrder) {
            existingToOrder.quantity += comp.replenish_quantity || comp.quantity || 0;
        } else {
            const toOrderRep = otherReps.find((r) => r.summary && r.summary.model === "to_order");
            product.to_order_replenishments.push({
                product_id: prodId,
                quantity: comp.replenish_quantity || comp.quantity || 0,
                uom_name: comp.uom_name || "",
                parent_name: parentName,
                parent_product_id: parentProductId,
                formatted_state: comp.formatted_state || _t("To Order"),
                state_class: 'text-bg-danger',
                receipt: (toOrderRep && toOrderRep.summary.receipt) || comp.receipt || null,
            });
        }
        return;
    }

    // Register non-sub-MO usages (stock / PO) aggregated by parent MO.
    // When there are no replenishments at all (plain stock component with
    // quantity already reserved) we still need a usage row for the parent.
    const hasNonSubMoRep = otherReps.length > 0;
    const hasSubMoRep = subMoReps.length > 0;

    if (hasNonSubMoRep || !hasSubMoRep) {
        // Aggregate into a single usage row keyed by parentProductId.
        const existingUsage = product.usages.find(
            (u) => u.parent_product_id === parentProductId
        );
        if (existingUsage) {
            existingUsage.quantity += comp.quantity || 0;
            existingUsage.total += moCost;
            existingUsage.prod_cost += realCost;
        } else {
            product.usages.push({
                parent_product_id: parentProductId,
                parent_name: parentName,
                quantity: comp.quantity || 0,
                uom_name: comp.uom_name || "",
                total: moCost,
                prod_cost: realCost,
                lead_time: false,
                route_name: "",
                route_detail: "",
                route_type: "",
                bom_id: false,
                parent_route_name: "",
                parent_route_detail: "",
                parent_route_type: "",
                parent_bom_id: false,
            });
        }
    }
}

// ---------------------------------------------------------------------------
// Internal helpers (continued)
// ---------------------------------------------------------------------------

/**
 * Process the components of a sub-MO replenishment, adding each one to the
 * category map and recursing further for any nested sub-MO replenishments.
 *
 * This is needed because `data.components[]` only contains direct components
 * of the main MO.  Each `mrp.production` replenishment carries its own
 * `components[]` array (populated by the Python backend recursively) which
 * must also be collected so that deep-level materials appear in the
 * "Components by Category" section.
 *
 * @param {Object} subMoRep        - A replenishment dict with model='mrp.production'
 * @param {Object} categoryMap     - Accumulator keyed by categ_id
 * @param {string} parentName      - Display name of the intermediate product this sub-MO produces
 * @param {number} parentProductId - product.product ID of that intermediate product
 */
function _processReplenishmentComponents(subMoRep, categoryMap, parentName, parentProductId) {
    for (const subCompWrapper of (subMoRep.components || [])) {
        const subComp = subCompWrapper.summary || subCompWrapper;
        const catId = subCompWrapper.categ_id !== undefined ? subCompWrapper.categ_id : (subComp.categ_id || 0);
        const catName = subCompWrapper.categ_name !== undefined ? subCompWrapper.categ_name : (subComp.categ_name || _t("Uncategorized"));
        const catAncestors = subCompWrapper.categ_ancestors !== undefined ? subCompWrapper.categ_ancestors : (subComp.categ_ancestors || [{ id: catId, name: catName }]);
        _addMoComponentEntry(
            categoryMap, subComp,
            subCompWrapper.replenishments || [],
            subComp.mo_cost || 0,
            subComp.real_cost || 0,
            parentName,
            parentProductId,
            catId,
            catName,
            catAncestors,
        );
        // Recurse further for any sub-MO replenishments of this sub-component.
        for (const rep of (subCompWrapper.replenishments || [])) {
            if (rep.summary && rep.summary.model === "mrp.production" && rep.components) {
                _processReplenishmentComponents(rep, categoryMap, subComp.name, subComp.product_id);
            }
        }
    }
}

/**
 * Process the workorders of a sub-MO replenishment and add each one to the
 * workcenter map, then recurse into any nested sub-MO replenishments so that
 * all levels of the manufacturing tree are represented in the Operations
 * by Work Center section.
 *
 * Requires that _get_operations_data (Python) injects workcenter_id /
 * workcenter_name into each detail dict; without that injection the operation
 * falls into the "Unknown" bucket but is still counted.
 *
 * @param {Object} subMoRep        - A replenishment dict with model='mrp.production'
 * @param {Object} workcenterMap   - Accumulator keyed by workcenter_id
 * @param {string} parentName      - Display name of the product this sub-MO produces
 * @param {number} parentProductId - product.product ID of that product
 */
function _processReplenishmentOperations(subMoRep, workcenterMap, parentName, parentProductId) {
    const opsDetails = (subMoRep.operations && subMoRep.operations.details) || [];
    const parentQty = subMoRep.summary ? (subMoRep.summary.quantity || 1) : 1;
    const parentUomName = subMoRep.summary ? (subMoRep.summary.uom_name || "") : "";

    for (const op of opsDetails) {
        const wcId = op.workcenter_id || 0;
        const wcName = op.workcenter_name || _t("Unknown");

        if (!workcenterMap[wcId]) {
            workcenterMap[wcId] = {
                id: wcId,
                name: wcName,
                total: 0,
                real_cost_total: 0,
                total_duration: 0,
                items: [],
            };
        }
        const wc = workcenterMap[wcId];
        wc.total += op.mo_cost || 0;
        wc.real_cost_total += op.real_cost || 0;
        wc.total_duration += op.quantity || 0;
        wc.items.push({
            name: op.name,
            link_id: op.id || false,
            duration: op.quantity || 0,
            total: op.mo_cost || 0,
            real_cost: op.real_cost || 0,
            state: op.state || "",
            formatted_state: op.formatted_state || op.state || "",
            state_class: getStateDecorator("mrp.workorder", op.state || ""),
            parent_name: parentName,
            parent_product_id: parentProductId,
            lead_time: false,
            route_name: "",
            route_detail: "",
            route_type: "",
            bom_id: false,
            parent_qty: parentQty,
            parent_uom_name: parentUomName,
            components: [],
        });
    }

    // Recurse into sub-MO replenishments of this sub-MO's own components.
    for (const compWrapper of (subMoRep.components || [])) {
        const subComp = compWrapper.summary || compWrapper;
        for (const rep of (compWrapper.replenishments || [])) {
            if (rep.summary && rep.summary.model === "mrp.production") {
                _processReplenishmentOperations(
                    rep, workcenterMap, subComp.name, subComp.product_id,
                );
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Collect MO component and operation costs from the flat get_report_values
 * data structure into category and workcenter accumulator maps.
 *
 * @param {Object} data - Raw data from report.mrp.report_mo_overview.get_report_values
 * @returns {{ categoryMap: Object, workcenterMap: Object }}
 */
export function collectMoCosts(data) {
    const categoryMap = {};
    const workcenterMap = {};
    const parentName = data.summary ? data.summary.name : "";
    const parentProductId = data.summary ? data.summary.product_id : 0;

    // ---- Components ----
    for (const compWrapper of (data.components || [])) {
        const comp = compWrapper.summary || compWrapper;
        // categ fields are on the wrapper level (not inside summary) to avoid
        // breaking MoOverviewLine's strict prop-shape validation.
        const catId = compWrapper.categ_id !== undefined ? compWrapper.categ_id : (comp.categ_id || 0);
        const catName = compWrapper.categ_name !== undefined ? compWrapper.categ_name : (comp.categ_name || _t("Uncategorized"));
        const catAncestors = compWrapper.categ_ancestors !== undefined ? compWrapper.categ_ancestors : (comp.categ_ancestors || [{ id: catId, name: catName }]);
        _addMoComponentEntry(
            categoryMap, comp,
            compWrapper.replenishments || [],
            comp.mo_cost || 0,
            comp.real_cost || 0,
            parentName,
            parentProductId,
            catId,
            catName,
            catAncestors,
        );
        // Recurse into sub-MO replenishments to collect their own components.
        for (const rep of (compWrapper.replenishments || [])) {
            if (rep.summary && rep.summary.model === "mrp.production" && rep.components) {
                _processReplenishmentComponents(rep, categoryMap, comp.name, comp.product_id);
            }
        }
    }

    // ---- Operations (workorders) ----
    // operations_workcenter_info is a top-level sibling of data.operations,
    // injected by _get_report_data to avoid polluting the 'operations' prop
    // shape that MoOverviewComponentsBlock validates strictly as {summary, details}.
    const opsDetails = (data.operations && data.operations.details) || [];
    const opsExtra = data.operations_workcenter_info || [];
    for (let i = 0; i < opsDetails.length; i++) {
        const op = opsDetails[i];
        const extra = opsExtra[i] || {};
        const wcId = extra.workcenter_id || 0;
        const wcName = extra.workcenter_name || _t("Unknown");

        if (!workcenterMap[wcId]) {
            workcenterMap[wcId] = {
                id: wcId,
                name: wcName,
                total: 0,
                real_cost_total: 0,
                total_duration: 0,
                items: [],
            };
        }
        const wc = workcenterMap[wcId];
        wc.total += op.mo_cost || 0;
        wc.real_cost_total += op.real_cost || 0;
        wc.total_duration += op.quantity || 0;
        wc.items.push({
            name: op.name,
            link_id: op.id || false,
            duration: op.quantity || 0,
            total: op.mo_cost || 0,
            real_cost: op.real_cost || 0,
            state: op.state || "",
            formatted_state: op.formatted_state || op.state || "",
            state_class: getStateDecorator("mrp.workorder", op.state || ""),
            parent_name: parentName,
            parent_product_id: parentProductId,
            lead_time: false,
            route_name: "",
            route_detail: "",
            route_type: "",
            bom_id: false,
            parent_qty: data.summary ? (data.summary.quantity || 1) : 1,
            parent_uom_name: data.summary ? (data.summary.uom_name || "") : "",
            components: [],
        });
    }

    // ---- Sub-MO Operations ----
    // For each sub-MO replenishment in the top-level components, recursively
    // collect all sub-MO workorders into the same workcenterMap so they
    // appear alongside the parent MO operations in the section.
    for (const compWrapper of (data.components || [])) {
        const comp = compWrapper.summary || compWrapper;
        for (const rep of (compWrapper.replenishments || [])) {
            if (rep.summary && rep.summary.model === "mrp.production") {
                _processReplenishmentOperations(rep, workcenterMap, comp.name, comp.product_id);
            }
        }
    }

    return { categoryMap, workcenterMap };
}

/**
 * Compute the full cost summary for a Manufacturing Order.
 *
 * Returns an object with the same shape as computeCostSummary() from the BOM
 * module so that BomCostSummarySection can render it without modification.
 * Column semantics differ:
 *   col1 (total / "BoM Cost" label in BomCostSummarySection defaults):
 *     → renamed to "MO Cost" by passing columnLabels prop
 *     → contains mo_cost (estimated / theoretical)
 *   col2 (prod_cost_total / "Product Cost" label):
 *     → renamed to "Real Cost"
 *     → contains real_cost (actual consumed)
 *
 * @param {Object} data - Raw report values from get_report_values
 * @returns {Object|false} Cost summary or false when MO has no data
 */
export function computeMoCostSummary(data) {
    if (!data || !data.summary) {
        return false;
    }

    const { categoryMap, workcenterMap } = collectMoCosts(data);

    // Build the category tree (same algorithm as BOM module)
    const categories = buildCategoryTree(categoryMap);
    const workcenters = Object.values(workcenterMap).sort(
        (a, b) => b.total - a.total,
    );

    if (!categories.length && !workcenters.length) {
        return false;
    }

    // Aggregate totals
    let totalMoCostComponents = 0;
    let totalRealCostComponents = 0;
    const sumTree = (nodes) => {
        for (const node of nodes) {
            totalMoCostComponents += node.total;
            totalRealCostComponents += node.prod_cost_total;
            // Reset to avoid double-counting: bubbleUp already propagated
            // child costs up; we only want root-level contributions here.
            // (total/prod_cost_total on root nodes already include children)
        }
    };
    // Use top-level nodes only (buildCategoryTree already summed children up)
    for (const root of categories) {
        totalMoCostComponents += root.total;
        totalRealCostComponents += root.prod_cost_total;
    }
    // Subtract double-add from the sumTree call above — actually just iterate
    // category roots directly:
    totalMoCostComponents = 0;
    totalRealCostComponents = 0;
    for (const root of categories) {
        totalMoCostComponents += root.total;
        totalRealCostComponents += root.prod_cost_total;
    }

    let totalMoCostOperations = 0;
    let totalRealCostOperations = 0;
    let totalDuration = 0;
    for (const wc of workcenters) {
        totalMoCostOperations += wc.total;
        totalRealCostOperations += wc.real_cost_total;
        totalDuration += wc.total_duration;
    }

    const grandTotalMoCost = totalMoCostComponents + totalMoCostOperations;
    const grandTotalRealCost = totalRealCostComponents + totalRealCostOperations;

    // Enrich category tree with percentages (no secondary currency for MO initially)
    enrichCategoryTree(categories, 0, totalMoCostComponents);

    // Enrich workcenter entries with percentages
    for (const wc of workcenters) {
        wc.percentage = totalMoCostOperations
            ? (wc.total / totalMoCostOperations) * 100 : 0;
        wc.total_usd = false;
        for (const item of wc.items) {
            item.percentage = totalMoCostOperations
                ? (item.total / totalMoCostOperations) * 100 : 0;
            item.total_usd = false;
        }
    }

    return {
        categories,
        workcenters,
        byproductCategories: [],   // MO: no byproduct cost breakdown
        subcontracting: [],        // MO: subcontracting deferred to a future extension
        totals: {
            components: totalMoCostComponents,
            components_usd: false,
            prod_cost: totalRealCostComponents,
            prod_cost_usd: false,
            operations: totalMoCostOperations,
            operations_usd: false,
            operations_duration: totalDuration,
            operations_real_cost: totalRealCostOperations,
            subcontracting: 0,
            subcontracting_usd: false,
            subcontracting_prod_cost: 0,
            subcontracting_prod_cost_usd: false,
            byproducts: 0,
            byproducts_usd: false,
            byproducts_prod_cost: 0,
            byproducts_prod_cost_usd: false,
            // Grand total col1 = total mo_cost (components + operations)
            total: grandTotalMoCost,
            total_usd: false,
            // Grand total col2 = total real_cost (components + operations)
            total_prod: grandTotalRealCost,
            total_prod_usd: false,
            // net = gross (no byproducts to deduct in MO mode)
            net_bom: grandTotalMoCost,
            net_bom_usd: false,
            net_prod: grandTotalRealCost,
            net_prod_usd: false,
        },
        currency_id: data.summary.currency_id || null,
    };
}
