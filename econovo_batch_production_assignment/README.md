# Econovo Batch Production Assignment

## Overview

This Odoo 17 module enables **mass/batch assignment and unassignment of manufacturing orders** directly from the list view, eliminating the need to manage materials manually one by one.

## Features

### ✨ Enhanced User Experience

1. **Dual Operation Mode Wizard**: Users can switch between assignment and unassignment modes:
   - **📍 Assignment Mode**: Analyze and assign materials to manufacturing orders
   - **📤 Unassignment Mode**: Analyze and unreserve materials from manufacturing orders

2. **Pre-Operation Analysis**: Detailed analysis of selected orders before execution:
   
   **For Assignment:**
   - **✅ Fully Assignable**: Orders with all materials available and ready
   - **⚠️ Partially Assignable**: Orders with some materials available but not all
   - **ℹ️ Already Assigned**: Orders that already have materials assigned
   - **❌ No Materials**: Orders with no materials available for assignment
   - **🚫 Invalid State**: Orders not in valid state (must be Confirmed or In Progress)

   **For Unassignment:**
   - **✅ Fully Unreservable**: Orders with all materials reserved and ready to unreserve
   - **⚠️ Partially Unreservable**: Orders with some materials reserved but not all
   - **❌ No Reservations**: Orders with no materials reserved for unreservation

3. **Dynamic Mode Switching**: Real-time analysis updates when switching between assignment/unassignment modes

4. **Comprehensive Result Messages**: After execution, users receive detailed feedback categorizing results and showing specific error details

### 🔧 Technical Features

- **Native Integration**: Uses Odoo's built-in assignment/unreservation logic
- **Dual Operation Modes**: Comprehensive assignment and unassignment functionality
- **Batch Processing**: Select multiple Manufacturing Orders and manage materials in one action
- **Smart Categorization**: Automatically analyzes and categorizes orders based on material availability/reservation status
- **Dynamic Mode Switching**: Real-time reanalysis when switching operation modes
- **Error Handling**: Robust error management with detailed logging and user feedback
- **Performance Optimized**: Efficient processing of large batches

## Installation

1. Copy the module to your Odoo addons directory:
   ```
   addons/econovo_batch_production_assignment/
   ```

2. Update the modules list in Odoo:
   ```
   Settings > Apps > Update Apps List
   ```

3. Search and install "Econovo Batch Production Assignment"

## Usage

### Assignment Workflow

1. **Navigate** to Manufacturing > Orders > Manufacturing Orders
2. **Select** one or multiple Manufacturing Orders from the list view
3. **Click** the "Action" button (⚙️ gear icon)
4. **Choose** "Batch Assign Materials"
5. **Review** the analysis summary in the confirmation wizard
6. **Confirm** to execute the assignment
7. **View** the detailed results notification

### Unassignment Workflow

1. **Navigate** to Manufacturing > Orders > Manufacturing Orders
2. **Select** one or multiple Manufacturing Orders from the list view
3. **Click** the "Action" button (⚙️ gear icon)
4. **Choose** "Batch Unassign Materials"
5. **Review** the analysis summary in the confirmation wizard (automatically in unassignment mode)
6. **Confirm** to execute the unassignment
7. **View** the detailed results notification

### Unified Wizard Workflow

1. **Navigate** to Manufacturing > Orders > Manufacturing Orders
2. **Select** one or multiple Manufacturing Orders from the list view
3. **Click** the "Action" button (⚙️ gear icon)
4. **Choose** either "Batch Assign Materials" or "Batch Unassign Materials"
5. **Switch Operation Mode** if needed using the radio buttons at the top
6. **Review** the dynamic analysis summary
7. **Confirm** to execute the selected operation
8. **View** the detailed results notification

### Analysis Categories Explained

#### Assignment Mode Categories

#### ✅ Fully Assignable
- All required materials are available in stock
- Orders will be completely assigned
- Ready for production

#### ⚠️ Partially Assignable  
- Some required materials are available
- Orders will be partially assigned
- Additional assignments may be needed later

#### ℹ️ Already Assigned
- Materials are already assigned to these orders
- No action needed
- Skipped during processing

#### ❌ No Materials Available
- No required materials are available in stock
- Cannot be assigned
- Check inventory levels

#### 🚫 Invalid State
- Orders are not in valid state for assignment
- Must be in "Confirmed" or "In Progress" state
- Update order status first

#### Unassignment Mode Categories

#### ✅ Fully Unreservable
- All materials are reserved and ready to unreserve
- Orders will have all materials unreserved
- Complete unreservation possible

#### ⚠️ Partially Unreservable
- Some materials are reserved but not all
- Orders will have partial unreservation
- Some materials may remain reserved

#### ❌ No Reservations
- No materials are currently reserved
- No action needed
- Skipped during processing

## Technical Details

### Architecture

- **Main Model**: `mrp.production` (extends Odoo's Manufacturing Orders)
- **Wizard Model**: `mrp.production.batch.assignment.wizard` (unified confirmation dialog)
- **Server Actions**: 
  - `action_batch_assign_production` (assignment from list view)
  - `action_batch_unassign_production` (unassignment from list view)

### Key Methods

```python
# Assignment workflow
def batch_production_assignment(self):
    """Processes batch assignment with categorized results"""

# Unassignment workflow  
def batch_production_unassignment(self):
    """Processes batch unassignment with categorized results"""

# Dual categorization methods
def _categorize_production_for_assignment(self, production):
    """Analyzes a single order's assignment status"""
    
def _categorize_production_for_unassignment(self, production):
    """Analyzes a single order's reservation status"""

# Execution methods
def _execute_batch_assignment(self):
    """Executes assignment using reception report logic"""
    
def _execute_batch_unassignment(self):
    """Executes unassignment using native do_unreserve"""
```

### Workflow Integration

The module integrates seamlessly with Odoo's native manufacturing workflow:

1. **Assignment Uses Reception Report Logic**: Leverages `report.stock.report_reception` for assignments
2. **Unassignment Uses Native Methods**: Uses Odoo's `do_unreserve()` for material unreservation
3. **Maintains Native Behavior**: Same logic as individual "Allocation" and "Unreserve" buttons
4. **Preserves Consistency**: All operations follow Odoo's standard rules and validations

## Compatibility

- **Odoo Version**: 17.0
- **Dependencies**: `mrp`, `stock`
- **Enterprise/Community**: Compatible with both

## Security

The module includes proper access controls:
- Manufacturing User: Can use batch assignment
- Manufacturing Manager: Full access to all features

## Troubleshooting

### Common Issues

#### Assignment Issues

**Issue**: "No materials available for assignment"
- **Solution**: Check inventory levels for required materials

**Issue**: "Invalid state for assignment"
- **Solution**: Ensure orders are in "Confirmed" or "In Progress" state

**Issue**: Orders show as "Already Assigned"
- **Solution**: Check if materials were previously assigned manually

#### Unassignment Issues

**Issue**: "No materials reserved for unreservation"
- **Solution**: Check if materials are actually reserved in the manufacturing order

**Issue**: Orders show as "No Reservations"
- **Solution**: Verify that materials were previously assigned/reserved

**Issue**: Partial unreservation occurs
- **Solution**: Some stock moves may be in states that prevent full unreservation

### Logging

The module provides detailed logging for debugging:
```python
_logger.info("Processing batch assignment for %d orders", len(productions))
_logger.info("Processing batch unassignment for %d orders", len(productions))
_logger.error("Error in assignment: %s", str(error))
_logger.error("Error in unassignment: %s", str(error))
```

## Support

For issues, improvements, or questions:
- **Author**: Jose D. Leonett
- **GitHub**: https://github.com/josedleonett
- **License**: AGPL-3

## Changelog

### Version 17.0.2.0.0
- ✨ **NEW**: Batch unassignment functionality
- ✨ **NEW**: Dual operation mode wizard (assign/unassign)
- ✨ **NEW**: Dynamic mode switching with real-time analysis
- ✨ **NEW**: Unassignment categorization and analysis
- ✨ **NEW**: Separate server action for unassignment
- 🔧 **IMPROVED**: Unified wizard interface
- 🔧 **IMPROVED**: Enhanced user experience with mode-specific messaging
- 🌍 **ADDED**: Spanish translations for unassignment features
- 🧪 **ADDED**: Comprehensive test coverage for unassignment scenarios

### Version 17.0.1.0.0
- ✨ **NEW**: Pre-assignment analysis wizard
- ✨ **NEW**: Detailed categorization of orders
- ✨ **NEW**: Confirmation dialog with summary
- ✨ **NEW**: Enhanced result messages
- 🔧 **IMPROVED**: Error handling and user feedback
- 🔧 **IMPROVED**: Performance optimization
- 🐛 **FIXED**: Edge cases in assignment logic

---

*This module follows Odoo development best practices and maintains compatibility with standard Odoo workflows.*