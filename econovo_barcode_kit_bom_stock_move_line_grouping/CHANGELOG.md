# Changelog

All notable changes to the Econovo Barcode Kit/BOM Stock Move Line Grouping module will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [17.0.1.0.0] - 2024-01-XX

### Added
- Initial release of Econovo Barcode Kit Grouping module for Odoo 17
- Visual grouping of kit/BOM components in stock barcode app
- Multi-location support (group components from different shelves)
- Collapse/expand functionality using native Odoo patterns
- Kit name display with component count badge
- Blue border and background styling for kit groups
- Source location abstraction in collapsed view ("3 locations" instead of specific shelves)
- Individual component location display in expanded view
- Warning indicators for kits with multiple destination locations
- SCSS styling with Bootstrap 5 compatibility
- Comprehensive README with usage examples and technical details
- Testing guide with manual test cases
- Full compatibility with `stock_barcode_mrp` (kit explosion)

### Technical Details
- Backend: Override `stock.picking._get_stock_barcode_data()` to expose BOM fields
- Frontend: Patch `BarcodePickingModel.groupKey()` and `get groupedLines` methods
- UI: Extend `GroupedLineComponent` template with kit-specific layout
- Assets: JavaScript modules, XML templates, SCSS styles

### Dependencies
- `stock_barcode` (Enterprise)
- `mrp` (Manufacturing)
- `stock_barcode_mrp` (Enterprise)

### Known Limitations
- None identified in initial release

---

## [Unreleased]

### Planned Features
- [ ] Auto-validation option for complete kits
- [ ] Kit progress indicator (scanned components vs total)
- [ ] Configurable grouping strategies (by kit, by location, by destination)
- [ ] Support for nested kits (kit within kit)
- [ ] Multi-company support with location-based grouping rules

### Under Consideration
- Performance optimizations for very large kits (100+ components)
- Alternative UI layouts (grid view, card view)
- Integration with quality control module
- Barcode scanning enhancements (scan kit code to validate all components)

---

## Version History

| Version     | Date       | Changes Summary                          |
|-------------|------------|------------------------------------------|
| 17.0.1.0.0  | 2024-01-XX | Initial release for Odoo 17              |

---

## Migration Notes

### From No Module → v17.0.1.0.0
- No migration needed
- Install module and restart Odoo server
- Clear browser cache to load new assets
- No database changes required

### Future Migrations
- Will be documented here when new versions are released

---

## Support & Contribution

- **Author:** Jose D. Leonett
- **Repository:** https://github.com/josedleonett
- **Issues:** Report via GitHub issues
- **Pull Requests:** Welcome! Follow Odoo coding standards

---

## License

AGPL-3 - See LICENSE file for details
