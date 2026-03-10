/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";

// ---------------------------------------------------------------------------
// Pure utility functions extracted from bom_overview_component_patch.js
// so they can be shared between the patched BomOverviewComponent and the
// standalone BomCostSummaryView without any prototype coupling.
// ---------------------------------------------------------------------------

/**
 * Recursively walks the BOM tree collecting leaf component,
 * operation, and byproduct costs, tracking parent product for traceability.
 *
 * @param {Object} node - Current BOM tree node
 * @param {Object} categoryMap - Accumulator for component category groupings
 * @param {Object} workcenterMap - Accumulator for workcenter groupings
 * @param {Object} byproductCategoryMap - Accumulator for byproduct category groupings
 * @param {number} [ancestorCostShare=1.0] - Accumulated cost_share factor
 */
export function collectCosts(node, categoryMap, workcenterMap, byproductCategoryMap, ancestorCostShare = 1.0) {
    const parentName = node.name;
    const parentProductId = node.product_id;

    const parentRouteInfo = {
        route_name: node.route_name || "",
        route_detail: node.route_detail || "",
        route_type: node.route_type || "",
        bom_id: node.bom_id || false,
    };

    const nodeCostShare =
        node.cost_share !== undefined && node.cost_share !== null
            ? node.cost_share
            : 1.0;
    const effectiveCostShare = ancestorCostShare * nodeCostShare;

    // Collect operations at this BOM level
    if (node.operations) {
        for (const op of node.operations) {
            const wcId = op.workcenter_id || 0;
            const wcName = op.workcenter_name || _t("Unknown");
            if (!workcenterMap[wcId]) {
                workcenterMap[wcId] = {
                    id: wcId,
                    name: wcName,
                    total: 0,
                    total_duration: 0,
                    items: [],
                };
            }
            const adjustedCost = (op.bom_cost || 0) * effectiveCostShare;
            const opDuration = op.quantity || 0;
            workcenterMap[wcId].total += adjustedCost;
            workcenterMap[wcId].total_duration += opDuration;
            workcenterMap[wcId].items.push({
                name: op.operation_name || op.name,
                link_id: op.link_id || false,
                duration: opDuration,
                total: adjustedCost,
                parent_name: parentName,
                parent_product_id: parentProductId,
                lead_time: node.lead_time || false,
                route_name: node.route_name || "",
                route_detail: node.route_detail || "",
                route_type: node.route_type || "",
                bom_id: node.bom_id || false,
            });
        }
    }

    // Collect byproducts at this BOM level.
    // bp.bom_cost is already expressed in this node's cost units; scale only
    // by ancestorCostShare (not effectiveCostShare) since the byproduct's own
    // cost_share is already embedded inside bp.bom_cost.
    if (node.byproducts) {
        for (const bp of node.byproducts) {
            const catId = bp.categ_id || 0;
            const catName = bp.categ_name || _t("Uncategorized");
            if (!byproductCategoryMap[catId]) {
                byproductCategoryMap[catId] = {
                    id: catId,
                    name: catName,
                    total: 0,
                    prod_cost_total: 0,
                    products: {},
                    ancestors: bp.categ_ancestors || [
                        { id: catId, name: catName },
                    ],
                };
            }
            const adjustedCost = (bp.bom_cost || 0) * ancestorCostShare;
            const adjustedProdCost = (bp.prod_cost || 0) * ancestorCostShare;
            const cat = byproductCategoryMap[catId];
            cat.total += adjustedCost;
            cat.prod_cost_total += adjustedProdCost;

            // Group by product (link_id = product.product.id or template.id)
            const prodKey = bp.link_id || bp.id;
            if (!cat.products[prodKey]) {
                cat.products[prodKey] = {
                    product_id: prodKey,
                    name: bp.name,
                    link_id: bp.link_id || false,
                    link_model: bp.link_model || "product.product",
                    total: 0,
                    prod_cost_total: 0,
                    usages: [],
                };
            }
            const bpProduct = cat.products[prodKey];
            bpProduct.total += adjustedCost;
            bpProduct.prod_cost_total += adjustedProdCost;

            const existingUsage = bpProduct.usages.find(
                (u) => u.parent_product_id === parentProductId
            );
            if (existingUsage) {
                existingUsage.quantity += bp.quantity || 0;
                existingUsage.total += adjustedCost;
                existingUsage.prod_cost += adjustedProdCost;
            } else {
                bpProduct.usages.push({
                    parent_product_id: parentProductId,
                    parent_name: parentName,
                    quantity: bp.quantity || 0,
                    uom_name: bp.uom_name,
                    total: adjustedCost,
                    prod_cost: adjustedProdCost,
                });
            }
        }
    }

    // Process components
    if (node.components) {
        for (const comp of node.components) {
            if (comp.type === "bom" && comp.components) {
                // Sub-BOM: recurse
                collectCosts(comp, categoryMap, workcenterMap, byproductCategoryMap, effectiveCostShare);
            } else {
                // Leaf component: add to category -> product -> usages
                const catId = comp.categ_id || 0;
                const catName = comp.categ_name || _t("Uncategorized");
                if (!categoryMap[catId]) {
                    categoryMap[catId] = {
                        id: catId,
                        name: catName,
                        total: 0,
                        prod_cost_total: 0,
                        products: {},
                        ancestors: comp.categ_ancestors || [
                            { id: catId, name: catName },
                        ],
                    };
                }
                const adjustedCost = (comp.bom_cost || 0) * effectiveCostShare;
                const adjustedProdCost = (comp.prod_cost || 0) * effectiveCostShare;
                const cat = categoryMap[catId];
                cat.total += adjustedCost;
                cat.prod_cost_total += adjustedProdCost;

                const prodId = comp.product_id;
                if (!cat.products[prodId]) {
                    cat.products[prodId] = {
                        product_id: prodId,
                        name: comp.name,
                        link_id: comp.link_id || prodId,
                        link_model: comp.link_model || "product.product",
                        total: 0,
                        prod_cost_total: 0,
                        usages: [],
                        // Availability: stock levels for this component product.
                        // All usages share the same stock data, so capture it once.
                        quantity_available: comp.quantity_available !== undefined
                            ? comp.quantity_available : false,
                        quantity_on_hand: comp.quantity_on_hand !== undefined
                            ? comp.quantity_on_hand : false,
                        availability_state: comp.availability_state || false,
                        availability_display: comp.availability_display || "",
                    };
                }
                const product = cat.products[prodId];
                product.total += adjustedCost;
                product.prod_cost_total += adjustedProdCost;

                const existingUsage = product.usages.find(
                    (u) => u.parent_product_id === parentProductId
                );
                if (existingUsage) {
                    existingUsage.quantity += comp.quantity || 0;
                    existingUsage.total += adjustedCost;
                    existingUsage.prod_cost += adjustedProdCost;
                } else {
                    product.usages.push({
                        parent_product_id: parentProductId,
                        parent_name: parentName,
                        quantity: comp.quantity || 0,
                        uom_name: comp.uom_name,
                        total: adjustedCost,
                        prod_cost: adjustedProdCost,
                        lead_time: comp.lead_time || false,
                        route_name: comp.route_name || "",
                        route_detail: comp.route_detail || "",
                        route_type: comp.route_type || "",
                        bom_id: comp.bom_id || false,
                        parent_route_name: parentRouteInfo.route_name,
                        parent_route_detail: parentRouteInfo.route_detail,
                        parent_route_type: parentRouteInfo.route_type,
                        parent_bom_id: parentRouteInfo.bom_id,
                    });
                }
            }
        }
    }
}

/**
 * Builds a hierarchical category tree from the flat leaf-category map.
 *
 * @param {Object} categoryMap - Flat map keyed by leaf categ_id
 * @returns {Array} Root-level tree nodes sorted by total descending
 */
export function buildCategoryTree(categoryMap) {
    const nodeMap = {};
    const roots = [];

    for (const leaf of Object.values(categoryMap)) {
        const ancestors = leaf.ancestors;
        let parentChildren = roots;

        for (let i = 0; i < ancestors.length; i++) {
            const anc = ancestors[i];

            if (!nodeMap[anc.id]) {
                const node = {
                    id: anc.id,
                    name: anc.name,
                    depth: i,
                    total: 0,
                    prod_cost_total: 0,
                    children: [],
                    products: [],
                };
                nodeMap[anc.id] = node;
                parentChildren.push(node);
            } else {
                const node = nodeMap[anc.id];
                if (!parentChildren.includes(node)) {
                    parentChildren.push(node);
                    const rootIdx = roots.indexOf(node);
                    if (rootIdx !== -1 && parentChildren !== roots) {
                        roots.splice(rootIdx, 1);
                    }
                }
            }

            const node = nodeMap[anc.id];

            if (i === ancestors.length - 1) {
                node.products = Object.values(leaf.products)
                    .sort((a, b) => b.total - a.total);
                node.total += leaf.total;
                node.prod_cost_total += leaf.prod_cost_total;
            }

            parentChildren = node.children;
        }
    }

    const normaliseDepth = (nodes, depth) => {
        for (const n of nodes) {
            n.depth = depth;
            normaliseDepth(n.children, depth + 1);
        }
    };
    normaliseDepth(roots, 0);

    const bubbleUp = (node) => {
        for (const child of node.children) {
            bubbleUp(child);
            node.total += child.total;
            node.prod_cost_total += child.prod_cost_total;
        }
    };
    for (const root of roots) {
        bubbleUp(root);
    }

    const sortTree = (nodes) => {
        nodes.sort((a, b) => b.total - a.total);
        for (const n of nodes) {
            sortTree(n.children);
        }
    };
    sortTree(roots);

    return roots;
}

/**
 * Recursively enrich category tree nodes with percentage and USD amounts.
 *
 * @param {Array} nodes - Array of tree nodes at current level
 * @param {number} rate - USD conversion rate (0 if no secondary currency)
 * @param {number} totalComponents - Grand total of all component costs (bom_cost basis)
 */
export function enrichCategoryTree(nodes, rate, totalComponents) {
    for (const node of nodes) {
        node.percentage = totalComponents
            ? (node.total / totalComponents) * 100 : 0;
        node.total_usd = rate ? node.total * rate : false;
        node.prod_cost_total_usd = rate
            ? node.prod_cost_total * rate : false;

        for (const prod of node.products) {
            prod.percentage = totalComponents
                ? (prod.total / totalComponents) * 100 : 0;
            prod.total_usd = rate ? prod.total * rate : false;
            prod.prod_cost_total_usd = rate
                ? prod.prod_cost_total * rate : false;
            for (const usage of prod.usages) {
                usage.percentage = totalComponents
                    ? (usage.total / totalComponents) * 100 : 0;
                usage.total_usd = rate ? usage.total * rate : false;
                usage.prod_cost_usd = rate
                    ? usage.prod_cost * rate : false;
            }
        }

        enrichCategoryTree(node.children, rate, totalComponents);
    }
}

/**
 * Adds prod_cost_percentage to every node, product and usage in a byproduct
 * category tree.  This is the second % shown in the byproducts section:
 * prod_cost_total / totalByproductsProdCost * 100.
 * Always meaningful, even when bom_cost = 0 (cost_share = 0%).
 *
 * @param {Array} nodes - Byproduct category tree nodes
 * @param {number} totalProdCost - Grand total of byproducts prod_cost (denominator)
 */
export function enrichByproductProdCostPct(nodes, totalProdCost) {
    for (const node of nodes) {
        node.prod_cost_percentage = totalProdCost
            ? (node.prod_cost_total / totalProdCost) * 100 : 0;
        for (const prod of node.products) {
            prod.prod_cost_percentage = totalProdCost
                ? (prod.prod_cost_total / totalProdCost) * 100 : 0;
            for (const usage of prod.usages) {
                usage.prod_cost_percentage = totalProdCost
                    ? (usage.prod_cost / totalProdCost) * 100 : 0;
            }
        }
        enrichByproductProdCostPct(node.children, totalProdCost);
    }
}

/** * Orchestrates the three lower-level functions to produce the full
 * costSummary object consumed by BomCostSummarySection.
 *
 * @param {Object} data - The BOM data tree (state.bomData / bomData["lines"])
 * @param {Object|false} secondaryCurrency - USD currency info or false
 * @returns {Object|false} The costSummary object, or false if nothing to show
 */
export function computeCostSummary(data, secondaryCurrency) {
    const categoryMap = {};
    const workcenterMap = {};
    const byproductCategoryMap = {};
    collectCosts(data, categoryMap, workcenterMap, byproductCategoryMap);

    const rate = secondaryCurrency ? secondaryCurrency.rate : 0;

    const categories = buildCategoryTree(categoryMap);
    const workcenters = Object.values(workcenterMap).sort(
        (a, b) => b.total - a.total
    );
    const byproductCategories = buildCategoryTree(byproductCategoryMap);

    if (categories.length === 0 && workcenters.length === 0 && byproductCategories.length === 0) {
        return false;
    }

    const totalComponents = categories.reduce((s, c) => s + c.total, 0);
    const totalProdCost = categories.reduce((s, c) => s + c.prod_cost_total, 0);
    const totalOperations = workcenters.reduce((s, w) => s + w.total, 0);
    const totalDuration = workcenters.reduce((s, w) => s + w.total_duration, 0);
    const totalByproducts = byproductCategories.reduce((s, c) => s + c.total, 0);
    const totalByproductsProdCost = byproductCategories.reduce((s, c) => s + c.prod_cost_total, 0);
    // Byproducts reduce the net BOM cost (their bom_cost is allocated away
    // from the main product via cost_share).
    const totalBom = totalComponents + totalOperations - totalByproducts;
    const totalProd = totalProdCost + totalOperations;

    enrichCategoryTree(categories, rate, totalComponents);
    // bom_cost-based % for byproducts (native: 0 when cost_share=0)
    enrichCategoryTree(byproductCategories, rate, totalByproducts);
    // prod_cost-based % for byproducts (always meaningful)
    enrichByproductProdCostPct(byproductCategories, totalByproductsProdCost);

    for (const wc of workcenters) {
        wc.percentage = totalOperations
            ? (wc.total / totalOperations) * 100 : 0;
        wc.total_usd = rate ? wc.total * rate : false;
        for (const item of wc.items) {
            item.percentage = totalOperations
                ? (item.total / totalOperations) * 100 : 0;
            item.total_usd = rate ? item.total * rate : false;
        }
    }

    return {
        categories,
        workcenters,
        byproductCategories,
        totals: {
            components: totalComponents,
            components_usd: rate ? totalComponents * rate : false,
            prod_cost: totalProdCost,
            prod_cost_usd: rate ? totalProdCost * rate : false,
            operations: totalOperations,
            operations_usd: rate ? totalOperations * rate : false,
            operations_duration: totalDuration,
            byproducts: totalByproducts,
            byproducts_usd: rate ? totalByproducts * rate : false,
            byproducts_prod_cost: totalByproductsProdCost,
            byproducts_prod_cost_usd: rate ? totalByproductsProdCost * rate : false,
            total: totalBom,
            total_usd: rate ? totalBom * rate : false,
            total_prod: totalProd,
            total_prod_usd: rate ? totalProd * rate : false,
            // Net product cost = total catalogue cost of inputs minus recoverable
            // value of all byproducts at their standard_price.  Can be negative
            // when byproducts are worth more than the components (valid scenario).
            net_prod: totalProd - totalByproductsProdCost,
            net_prod_usd: rate ? (totalProd - totalByproductsProdCost) * rate : false,
        },
        currency_id: data.currency_id,
    };
}
