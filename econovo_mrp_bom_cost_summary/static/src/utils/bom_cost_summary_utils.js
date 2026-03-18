/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";

// ---------------------------------------------------------------------------
// Pure utility functions extracted from bom_overview_component_patch.js
// so they can be shared between the patched BomOverviewComponent and the
// standalone BomCostSummaryView without any prototype coupling.
// ---------------------------------------------------------------------------

/**
 * Inserts or merges a component entry into the category map.
 * Shared by leaf components and sub-BOM-level prod_cost entries.
 *
 * @param {Object} categoryMap
 * @param {Object} comp - BOM tree node providing categ/product metadata
 * @param {number} bomCost - Value to add to the BoM Cost aggregation
 * @param {number} prodCost - Value to add to the Product Cost aggregation
 * @param {string} parentName
 * @param {number} parentProductId
 * @param {Object} parentRouteInfo
 */
function _addComponentEntry(categoryMap, comp, bomCost, prodCost, parentName, parentProductId, parentRouteInfo) {
    const catId = comp.categ_id || 0;
    const catName = comp.categ_name || _t("Uncategorized");
    if (!categoryMap[catId]) {
        categoryMap[catId] = {
            id: catId,
            name: catName,
            total: 0,
            prod_cost_total: 0,
            products: {},
            ancestors: comp.categ_ancestors || [{ id: catId, name: catName }],
        };
    }
    const cat = categoryMap[catId];
    cat.total += bomCost;
    cat.prod_cost_total += prodCost;

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
    product.total += bomCost;
    product.prod_cost_total += prodCost;

    const existingUsage = product.usages.find(
        (u) => u.parent_product_id === parentProductId
    );
    if (existingUsage) {
        existingUsage.quantity += comp.quantity || 0;
        existingUsage.total += bomCost;
        existingUsage.prod_cost += prodCost;
    } else {
        product.usages.push({
            parent_product_id: parentProductId,
            parent_name: parentName,
            quantity: comp.quantity || 0,
            uom_name: comp.uom_name,
            total: bomCost,
            prod_cost: prodCost,
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

/**
 * Recursively walks the BOM tree collecting component, operation, and
 * byproduct costs.
 *
 * BoM Cost column  — recursive leaf breakdown: every leaf component
 *   (including those deep inside sub-BOMs) contributes its server-side
 *   `bom_cost` (= standard_price × qty × factor, cost_share already
 *   applied by _get_bom_data).  This gives a full manufacturing-cost
 *   breakdown per product category.
 *
 * Product Cost column — native Odoo semantics: each DIRECT component
 *   contributes its own `prod_cost` (= component.standard_price × qty).
 *   For sub-BOM components the sub-BOM product's standard_price is used
 *   (same as native BOM Overview); its internal leaf components receive
 *   prod_cost = 0 so they don't double-count.
 *
 * @param {Object} node - Current BOM tree node
 * @param {Object} categoryMap - Accumulator for component category groupings
 * @param {Object} workcenterMap - Accumulator for workcenter groupings
 * @param {Object} byproductCategoryMap - Accumulator for byproduct category groupings
 * @param {boolean} skipProdCost - True when recursing inside a sub-BOM;
 *   prevents double-counting the sub-BOM's prod_cost in leaf entries.
 */
export function collectCosts(node, categoryMap, workcenterMap, byproductCategoryMap, skipProdCost = false) {
    const parentName = node.name;
    const parentProductId = node.product_id;

    const parentRouteInfo = {
        route_name: node.route_name || "",
        route_detail: node.route_detail || "",
        route_type: node.route_type || "",
        bom_id: node.bom_id || false,
    };

    // Build component→operation lookup for this BOM level.
    const compsByOpId = {};
    for (const comp of (node.components || [])) {
        const opId = comp.operation_id || null;
        if (!compsByOpId[opId]) compsByOpId[opId] = [];
        compsByOpId[opId].push(comp);
    }

    // Collect operations at this BOM level — use raw bom_cost from server
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
            const adjustedCost = op.bom_cost || 0;
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
                parent_qty: node.quantity || 1,
                parent_uom_name: node.uom_name || "",
                components: compsByOpId[op.link_id] || [],
            });
        }
    }

    // Collect byproducts at this BOM level.
    // bp.bom_cost is the cost-share-allocated portion already computed
    // server-side.  Use it as-is without any additional scaling.
    // Byproducts always use their own prod_cost regardless of skipProdCost
    // because each byproduct IS a distinct product with its own standard_price.
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
            const adjustedCost = bp.bom_cost || 0;
            const adjustedProdCost = bp.prod_cost || 0;
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

    // Process components.
    //
    // BoM Cost  → always recurse to collect real manufacturing costs from leaves.
    // Product Cost → native Odoo semantics:
    //   • Direct component (leaf): use comp.prod_cost (standard_price × qty).
    //   • Sub-BOM component: add ONE entry for the sub-product using its own
    //     comp.prod_cost (its standard_price × qty), then recurse with
    //     skipProdCost=true so the internal leaves contribute bom_cost only.
    if (node.components) {
        for (const comp of node.components) {
            if (comp.type === "bom" && comp.components) {
                // Sub-BOM: capture prod_cost at this level (native semantics).
                if (!skipProdCost) {
                    _addComponentEntry(
                        categoryMap, comp,
                        0,                   // bom_cost comes from recursed leaves
                        comp.prod_cost || 0, // standard_price × qty of the sub-product
                        parentName, parentProductId, parentRouteInfo
                    );
                }
                // Recurse for the full BoM Cost breakdown; skip prod_cost to
                // avoid double-counting the sub-BOM's standard_price.
                collectCosts(comp, categoryMap, workcenterMap, byproductCategoryMap, true);
            } else {
                // Leaf component: bom_cost and prod_cost both from server.
                _addComponentEntry(
                    categoryMap, comp,
                    comp.bom_cost || 0,
                    skipProdCost ? 0 : (comp.prod_cost || 0),
                    parentName, parentProductId, parentRouteInfo
                );
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
    // Gross: components + operations before byproduct cost_share deduction.
    const grossBom = totalComponents + totalOperations;
    // Net: gross minus the cost_share portion allocated to byproducts.
    // Mirrors native Odoo data.bom_cost (= grossBom × main product cost_share).
    const netBom = grossBom - totalByproducts;
    // Native Odoo Product Cost column = product.standard_price × quantity of the
    // FINISHED product being manufactured (data.prod_cost from server).
    // This intentionally differs from the body section subtotals, which show
    // the bottom-up sum of component prod_costs for per-category analysis.
    const rootProdCost = data.prod_cost || 0;

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
            // Row 1 — gross totals (before byproduct recovery)
            total: grossBom,
            total_usd: rate ? grossBom * rate : false,
            // Product Cost = standard_price of the finished product (native Odoo semantics).
            // NOTE: this does NOT equal the sum of the body section subtotals, which
            // show the bottom-up component prod_costs — same intentional asymmetry as native.
            total_prod: rootProdCost,
            total_prod_usd: rate ? rootProdCost * rate : false,
            // Row 3 — net totals (after byproduct recovery)
            // net_bom mirrors native Odoo data.bom_cost exactly.
            net_bom: netBom,
            net_bom_usd: rate ? netBom * rate : false,
            // net_prod: standard_price of finished product minus byproduct standard prices.
            // Can be negative when byproducts are worth more than the finished product price.
            net_prod: rootProdCost - totalByproductsProdCost,
            net_prod_usd: rate ? (rootProdCost - totalByproductsProdCost) * rate : false,
        },
        currency_id: data.currency_id,
    };
}
