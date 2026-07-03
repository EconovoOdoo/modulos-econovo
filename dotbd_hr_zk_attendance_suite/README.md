# ZKteco HR Attendance Suite - Complete Biometric Integration

**Version:** 18.0.2.2.0
**Author:** Rafiur Rahman Rafit
**Company:** Dot BD Solutions Limited
**License:** OPL-1
**Module Name:** `dotbd_hr_zk_attendance_suite`

---

## 🚀 Overview

The most comprehensive attendance management solution for Odoo 18, featuring seamless ZKteco biometric device integration, powerful real-time analytics dashboard, intelligent anomaly detection, and enterprise-grade reporting capabilities. Perfect for businesses of all sizes looking to automate attendance tracking and gain valuable workforce insights.

---

## ✨ Key Features

### 🔐 Advanced Biometric Integration
- **Multi-Device Support**: Connect unlimited ZKteco devices (uFace 202, uFace 800, ZK4500, K40, etc.)
- **Face & Fingerprint Recognition**: Support for all ZKteco biometric authentication methods
- **Auto Check-in/Check-out Mode (NEW)**: Intelligent mode that automatically determines check-in/check-out, ignoring device punch type - prevents HR configuration mistakes!
- **Duplicate Punch Prevention (NEW)**: Automatically ignores repeated punches within configurable time window (default: 2 minutes)
- **Traditional Mode**: Classic mode using device punch type for backward compatibility
- **Automatic Sync**: Real-time attendance data synchronization with configurable intervals
- **Device Management**: Centralized control panel for managing multiple devices
- **Attendance Validation**: Automatic check-in/check-out detection with intelligent pairing
- **Employee Mapping**: Auto-link device users with Odoo employees

### 📊 Real-time Analytics Dashboard
- **Interactive Visualizations**: Beautiful charts with Chart.js integration
- **Smart Filters**: Pre-configured date ranges (Today/Week/Month/Year/Custom)
- **Live Statistics**: Real-time attendance metrics and KPIs
- **Anomaly Alerts**: Instant detection of attendance issues
- **Department Analytics**: Filter by department, employee, or custom criteria
- **Export Capabilities**: Download dashboard data for further analysis

### 🔍 Intelligent Anomaly Detection
- **Missing Check-in/Check-out**: Automatic detection of incomplete attendance records
- **Duplicate Punch Detection**: Identify and flag duplicate biometric punches
- **Attendance Violations**: Track policy violations and unusual patterns
- **Automated Categorization**: Smart classification of different anomaly types
- **Anomaly Reports**: Dedicated reports for compliance and audit purposes
- **Issue Resolution Workflow**: Built-in approval process for handling anomalies

### ⏰ Late Check-in Management System
- **Configurable Tolerance**: Set grace periods (e.g., 5 minutes) before marking late
- **Automatic Penalty Calculation**: Define penalty amounts per minute/instance
- **Approval Workflow**: Four-state system (Draft/Approved/Refused/Deducted)
- **Payroll Integration**: Seamless connection with hr_payroll_community module
- **Late Analytics Dashboard**: Track late trends and patterns by employee/department
- **Email Notifications**: Automatic alerts for late arrivals (optional)
- **Penalty Waiver System**: Allow managers to approve/refuse penalties

### 📅 Professional Attendance Sheets
- **Calendar-Style Layout**: Excel-like monthly attendance sheets
- **Color-Coded Status**: Visual indicators for Present/Absent/Late/Leave/Weekend/Holidays
- **Multiple Export Formats**: Generate PDF and Excel reports
- **Combined or Individual**: Choose between company-wide or per-employee sheets
- **Rich Statistics**: Work hours, late minutes, attendance rates, and rankings
- **Department Filtering**: Generate reports by department or employee groups
- **Time Off Integration**: Automatic display of approved leaves and public holidays

### 📈 Comprehensive Reporting Suite
- **Summary Reports**: Aggregated attendance statistics by employee/period
- **Detailed Daily Reports**: Complete day-by-day breakdown with check-in/out times
- **Late Check-in Reports**: Comprehensive penalty tracking with employee summaries
- **Anomaly Reports**: Dedicated reports for attendance issues and violations (NEW in v2.1.0)
- **Excel Export**: Professional XLSX reports with formatting and charts
- **PDF Generation**: Print-ready reports with company branding
- **Custom Date Ranges**: Flexible filtering for any time period
- **Department Analytics**: Group reports by organizational structure

### 🎯 Enterprise Features
- **Time Off Integration**: Seamless connection with Odoo Leave Management (hr_holidays)
- **Public Holidays**: Automatic detection and display of company-wide holidays
- **Working Calendar**: Respect employee working schedules and shifts
- **Overtime Tracking**: Calculate overtime and undertime hours automatically
- **Multi-Company Support**: Works with multiple companies in same database
- **Access Control**: Role-based permissions for HR managers and employees
- **Audit Trail**: Complete history of attendance modifications
- **Data Security**: Enterprise-grade security and data protection

### 💼 Payroll Integration (Optional)
- **Automatic Deductions**: Late penalties automatically added to payslips
- **Salary Rule**: Pre-configured deduction rule for late check-ins
- **Payslip Line Items**: Transparent display of penalty deductions
- **Integration with hr_payroll_community**: Seamless connection with community payroll module

---

## 📦 Installation

### Prerequisites

**Python Dependencies:**
```bash
pip install pyzk xlsxwriter
```

**System Requirements:**
- Odoo 18.0 (Community or Enterprise)
- PostgreSQL 12+
- Python 3.10+
- Network access to ZKteco devices

### Installation Steps

1. **Download the module:**
   ```bash
   cd /path/to/odoo/addons
   # Download or extract the module to dotbd_hr_zk_attendance_suite folder
   ```

2. **Install Python dependencies:**
   ```bash
   pip install pyzk xlsxwriter
   ```

3. **Set proper permissions:**
   ```bash
   sudo chown -R odoo:odoo dotbd_hr_zk_attendance_suite
   sudo chmod -R 755 dotbd_hr_zk_attendance_suite
   ```

4. **Restart Odoo server:**
   ```bash
   sudo systemctl restart odoo
   ```

5. **Update Apps List:**
   - Go to Odoo Apps menu
   - Click "Update Apps List"

6. **Install the module:**
   - Search for "ZKteco HR Attendance Suite"
   - Click "Install"

---

## ⚙️ Configuration

### 1. Biometric Device Setup

**Navigate to:** Attendance → Biometric Device → Biometric Device

**Add New Device:**
1. Click "Create"
2. Fill in device details:
   - **Device Name**: Give your device a name (e.g., "Main Entrance uFace 202")
   - **Device IP**: IP address of ZKteco device (e.g., 192.168.1.100)
   - **Port**: Usually 4370 (default for ZKteco devices)
   - **Location**: Physical location of device (e.g., "Head Office - Main Entrance")
   - **Company**: Select company (multi-company support)
3. Click "Save"
4. Click "Test Connection" to verify connectivity

**Auto-Sync Configuration:**
- Enable automatic synchronization in Settings
- Set sync interval (default: 15 minutes)
- Configure in: Settings → Technical → Scheduled Actions → "Biometric Device Auto Sync"

### 2. Late Check-in Settings

**Navigate to:** Settings → Attendance → Late Check-in Configuration

**Configure:**
- **Enable Late Check-in Tracking**: Turn on/off late tracking
- **Default Late Tolerance**: Minutes to allow before marking as late (e.g., 10 minutes)
- **Penalty Calculation Method**:
  - Fixed amount per late incident
  - Amount per late minute
- **Default Penalty Amount**: Amount to deduct (e.g., 50.00)
- **Auto-Approve Late Check-ins**: Enable automatic approval workflow

**Per-Employee Settings:**
- Navigate to: Employees → Select Employee → Attendance Tab
- Set individual late tolerance for specific employees
- Override default penalty amounts if needed

### 3. Working Hours Configuration

**Navigate to:** Employees → Employee → Working Times

- Set expected working schedule for each employee
- Define check-in and check-out times (e.g., 9:00 AM - 5:00 PM)
- Configure break times
- This is used to calculate late arrivals and work hours

### 4. Employee Device ID Mapping

**Navigate to:** Employees → Employee → Attendance Tab

- Set **ZK Device User ID** for each employee
- This ID should match the user ID on the biometric device
- Required for automatic attendance sync

---

## 📖 Usage Guide

### Viewing Attendance Dashboard

1. **Navigate to:** Attendance → Attendance Dashboard
2. **Select Date Range:**
   - Click "Today" for today's data
   - Click "This Week" for current week
   - Click "This Month" for current month
   - Click "This Year" for current year
   - Click "Custom Range" to select specific dates
3. **View Analytics:**
   - Total attendance issues
   - Late check-in statistics
   - Employee attendance summary
   - Daily trends and interactive charts
   - Anomaly alerts and notifications

### Managing Biometric Devices

**Sync Attendance Data:**
1. Navigate to: Attendance → Biometric Device → Biometric Device
2. Select your device
3. Click "Download Attendance"
4. Wait for synchronization to complete
5. Review synced records in Attendance → Daily Attendance

**Manual Sync:**
- Use "Clear Attendance" to reset device data (use with caution)
- Use "Test Connection" to verify device connectivity
- Check connection status indicator on device form

### Generating Attendance Sheets

1. **Navigate to:** Attendance → Employee Attendance Sheet
2. **Select Parameters:**
   - **Month**: Choose month (e.g., October)
   - **Year**: Choose year (e.g., 2025)
   - **Employees**: Leave empty for all, or select specific employees
   - **Report Format**: Choose Excel or PDF
   - **Sheet Type**: Combined (all in one sheet) or Individual (separate sheets)
3. **Click "Generate Report"**
4. **Download** the generated file

**Understanding the Attendance Sheet:**
- **P** = Present (Green background)
- **A** = Absent (Red background)
- **L** = Late (Orange background)
- **Leave** = On approved leave (Blue background)
- **Holiday** = Public holiday (Purple background)
- **-** = Weekend (Gray background)
- Right columns show totals: Present days, Absent days, Late days, Work hours

### Managing Late Check-ins

**View Late Check-ins:**
- Navigate to: Attendance → Late Check-in

**Approve/Refuse Late Check-ins:**
1. Open a late check-in record
2. Review details: Employee, Date, Late Minutes, Penalty Amount
3. Click "Approve" to confirm penalty
4. Click "Refuse" to waive penalty
5. Click "Mark as Deducted" after payroll processing
6. If payroll integration is enabled, approved penalties will be deducted automatically

**Bulk Actions:**
- Select multiple late check-in records
- Use Actions menu to approve/refuse in bulk
- Export data for external processing

### Generating Reports

**Navigate to:** Attendance → Reports → Generate Attendance Report

**Report Types:**

1. **Summary Report:**
   - Aggregated attendance statistics by employee
   - Total present/absent/late days
   - Work hours and overtime
   - Attendance percentage

2. **Detailed Report:**
   - Day-by-day attendance breakdown
   - Check-in and check-out times
   - Work hours per day
   - Late minutes per day

3. **Late Check-in Report:**
   - Comprehensive late arrival tracking
   - Penalty amounts and approval status
   - Late trends by employee
   - Department-wise late summaries

4. **Anomaly Report (NEW):**
   - Missing check-in/check-out records
   - Duplicate punch detection
   - Attendance violations
   - Categorized by anomaly type with color coding

**Generate Report:**
1. Select report type
2. Choose date range
3. Select employees (optional)
4. Click "Generate Report"
5. Click "Download Report" to get Excel file

### Viewing Attendance Anomalies

**Navigate to:** Attendance → Attendance Anomalies

**View by Type:**
- **Missing Check-in**: Employees with check-out but no check-in
- **Missing Check-out**: Employees who forgot to check out
- **Duplicate Check-in**: Multiple check-ins on same day

**Actions:**
- Click on an anomaly to view details
- Review related attendance records
- Correct data manually if needed
- Generate anomaly reports for compliance

---

## 🔧 Troubleshooting

### Device Connection Issues

**Problem:** Cannot connect to ZKteco device

**Solutions:**
1. Verify device IP address and port (default: 4370)
2. Check network connectivity: `ping <device-ip>`
3. Ensure firewall allows port 4370:
   ```bash
   sudo ufw allow 4370/tcp
   ```
4. Verify device is powered on and accessible on network
5. Check device admin settings for SDK/API access enabled
6. Try accessing device web interface to confirm it's online

### Attendance Data Not Syncing

**Problem:** Attendance data not updating from device

**Solutions:**
1. Check device connection status (should show "Connected")
2. Verify cron job is running: Settings → Technical → Scheduled Actions
3. Manually trigger sync: Device → Download Attendance
4. Check device has attendance data stored (access device directly)
5. Review Odoo logs for sync errors:
   ```bash
   tail -f /var/log/odoo/odoo.log | grep "biometric"
   ```
6. Verify employee Device IDs are mapped correctly

### Late Check-in Not Calculating

**Problem:** Late check-ins not being detected or calculated

**Solutions:**
1. Verify working hours are configured for employees
2. Check late tolerance settings in Settings → Attendance
3. Ensure attendance records have valid check-in times
4. Review employee's resource calendar (working schedule)
5. Check if late check-in tracking is enabled globally
6. Verify employee has a valid work schedule assigned

### Reports Not Generating

**Problem:** Excel/PDF reports fail to generate

**Solutions:**
1. Verify xlsxwriter is installed: `pip install xlsxwriter`
2. For PDF: Check wkhtmltopdf is installed:
   ```bash
   sudo apt-get install wkhtmltopdf
   ```
3. Check file permissions in Odoo filestore:
   ```bash
   sudo chown -R odoo:odoo /var/lib/odoo
   ```
4. Review Odoo logs for error messages
5. Try with smaller date range or fewer employees
6. Clear browser cache and try again

### Anomaly Report 404 Error (FIXED in v2.1.0)

**Problem:** Anomaly report download returns 404 error

**Solution:** Upgrade to version 2.1.0 or later where the anomaly report generation has been fully implemented.

---

## 📁 Module Structure

```
dotbd_hr_zk_attendance_suite/
├── controllers/
│   ├── __init__.py
│   └── attendance_anomaly_dashboard.py    # Dashboard controller
├── data/
│   ├── ir_cron_biometric.xml              # Scheduled actions
│   ├── late_check_in_data.xml             # Late check-in defaults
│   └── salary_rule_data.xml               # Payroll integration
├── models/
│   ├── __init__.py
│   ├── attendance_anomaly_analysis.py      # Issue detection (SQL view)
│   ├── attendance_report_wizard.py         # Report generator
│   ├── attendance_summary_analysis.py      # Summary calculations
│   ├── biometric_device_details.py         # Device management
│   ├── daily_attendance.py                 # Daily attendance records
│   ├── employee_attendance_sheet_wizard.py # Attendance sheet generator
│   ├── hr_attendance.py                    # Attendance model extension
│   ├── hr_employee.py                      # Employee model extension
│   ├── hr_employee_public.py               # Public employee view
│   ├── hr_payslip.py                       # Payroll integration
│   ├── late_check_in.py                    # Late check-in management
│   ├── res_config_settings.py              # Settings configuration
│   └── zk_machine_attendance.py            # ZKteco device communication
├── security/
│   └── ir.model.access.csv                 # Access rights and rules
├── static/
│   └── description/
│       ├── banner.png                      # Module banner (1200x630)
│       ├── icon.png                        # Module icon (256x256)
│       └── index.html                      # Odoo Apps Store description
├── views/
│   ├── templates/
│   │   ├── attendance_anomaly_dashboard.xml    # Dashboard template
│   │   └── employee_attendance_sheet_report.xml # PDF report template
│   ├── attendance_anomaly_analysis_views.xml
│   ├── attendance_anomaly_dashboard_menu.xml
│   ├── attendance_report_wizard_views.xml
│   ├── biometric_device_attendance_menus.xml
│   ├── biometric_device_details_views.xml
│   ├── daily_attendance_views.xml
│   ├── employee_attendance_sheet_wizard_views.xml
│   ├── hr_attendance_views.xml
│   ├── hr_employee_views.xml
│   ├── hr_payslip_views.xml
│   ├── late_check_in_views.xml
│   └── res_config_settings_views.xml
├── __init__.py
├── __manifest__.py
├── ANOMALY_ANALYSIS_README.md             # Anomaly detection documentation
└── README.md                               # This file
```

---

## 🛠️ Technical Details

### Core Models

**biometric.device.details**
- Manages ZKteco device connections
- Fields: name, device_ip, port, location, company_id
- Methods: test_connection(), download_attendance(), clear_attendance()

**zk.machine.attendance**
- Stores raw attendance punches from devices
- Inherits from: hr.attendance
- Fields: employee_id, punching_time, punch_type, device_id_num, address_id

**attendance.anomaly.analysis**
- SQL view for attendance issue detection
- Fields: employee_id, attendance_date, anomaly_type, checkin_count, checkout_count
- Anomaly types: missing_checkout, duplicate_checkin, missing_checkin

**late.check.in**
- Manages late arrival records and penalties
- Fields: employee_id, date, late_minutes, penalty_amount, state
- States: draft, approved, refused, deducted

**daily.attendance**
- Daily attendance summary records
- Fields: employee_id, attendance_date, check_in, check_out, total_hours

**attendance.report.wizard**
- Transient model for report generation
- Generates: Summary, Detailed, Late Check-in, Anomaly reports
- Supports Excel export with xlsxwriter

### Controllers

**AttendanceAnomalyDashboard**
- Route: `/attendance/anomaly/dashboard`
- Methods: index(), get_data()
- Provides dashboard rendering and AJAX data
- Supports date range filtering and department selection

### Scheduled Actions

**Biometric Device Auto Sync**
- Interval: Every 15 minutes (configurable)
- Model: biometric.device.details
- Method: cron_download_attendance()
- Automatically downloads attendance from all active devices

### SQL Views

**attendance_anomaly_analysis**
- High-performance SQL view for anomaly detection
- Uses CTEs (Common Table Expressions) for efficiency
- Automatically categorizes attendance issues
- Updates in real-time as attendance data changes

---

## 🌐 Support & Services

### Getting Help

**Dot BD Solutions Limited**
- **Website**: https://dotbd.com
- **Email**: support@dotbd.com
- **Response Time**: 24-48 hours
- **Support Duration**: 90 days included with purchase

### What's Included

- ✅ Full source code with AGPL-3 license
- ✅ Comprehensive documentation
- ✅ Installation guide
- ✅ 90 days email support
- ✅ Free bug fixes and security patches
- ✅ Minor version updates included

### Custom Development Services

We offer professional customization services:
- Custom report formats and layouts
- Integration with other HR/payroll modules
- Additional biometric device brand support
- Custom attendance rules and policies
- Workflow customizations and automation
- Mobile app development
- API integrations
- Training and consultation

**Contact us for a quote:** support@dotbd.com

---

## 📄 License

This module is licensed under **AGPL-3** (GNU Affero General Public License v3.0).

### You are free to:
- ✅ Use the module commercially
- ✅ Modify the source code
- ✅ Distribute the module
- ✅ Use privately

### Under the conditions that you:
- ⚠️ Disclose source code
- ⚠️ Include original license and copyright
- ⚠️ State changes made
- ⚠️ Provide same license (AGPL-3) for derivative works

Full license text: https://www.gnu.org/licenses/agpl-3.0.html

---

## 📝 Changelog

### Version 18.0.2.2.0 (Current)
- ✅ **NEW**: Auto Check-in/Check-out Mode - Intelligent attendance processing that ignores device punch type
- ✅ **NEW**: Duplicate Punch Prevention - Automatically ignores repeated punches within configurable time window
- ✅ **NEW**: Traditional Mode - Maintains backward compatibility with device punch types
- ✅ **NEW**: Per-Device Configuration - Each device can have its own attendance mode and duplicate threshold
- ✅ Enhanced device management UI with mode explanations and help text
- ✅ Added comprehensive logging for auto and traditional modes
- ✅ Improved attendance processing logic with separate methods for each mode
- ✅ Added AUTO_MODE_FEATURE.md documentation with complete usage guide
- ✅ Updated README and index.html with new feature information

### Version 18.0.2.1.0
- ✅ **NEW**: Implemented complete Anomaly Report generation
- ✅ Fixed 404 error when downloading anomaly reports
- ✅ Enhanced anomaly report with color-coded anomaly types
- ✅ Added summary section to anomaly reports
- ✅ Module refactoring and professional rebranding
- ✅ Updated module name to `dotbd_hr_zk_attendance_suite`
- ✅ Enhanced __manifest__.py with pricing and detailed metadata
- ✅ Created new professional index.html without image dependencies
- ✅ Updated documentation and README
- ✅ Resolved field label conflicts with other biometric modules

### Version 18.0.2.0.0
- Added Employee Attendance Sheet feature
- Calendar-style monthly attendance reports
- Excel and PDF export capabilities
- Per-employee and combined sheet options
- Color-coded attendance status
- Time Off (Leave) integration
- Public Holidays detection and display
- Complete rebranding to Dot BD Solutions Limited
- Enhanced module description and documentation

### Version 18.0.1.0.0
- Initial release for Odoo 18
- ZKteco device integration via pyzk library
- Real-time attendance dashboard
- Late check-in management with penalties
- Attendance anomaly detection
- Comprehensive report generation
- Payroll integration (optional)

---

## ❓ FAQ

**Q: What is Auto Check-in/Check-out Mode?**
A: Auto Mode is an intelligent feature that automatically determines whether a fingerprint punch should be a check-in or check-out, completely ignoring the device's punch type setting. First punch = check-in, second punch = check-out, third punch = check-in (alternates). This prevents HR configuration mistakes!

**Q: Should I use Auto Mode or Traditional Mode?**
A: Auto Mode is recommended for most installations because it prevents HR mistakes and simplifies device configuration. Use Traditional Mode only if you need to respect device punch types for specific workflows.

**Q: How does duplicate punch prevention work?**
A: If an employee punches multiple times within the configured time window (default: 2 minutes), only the first punch is recorded. This prevents accidental duplicate entries when employees punch repeatedly.

**Q: Can I set different modes for different devices?**
A: Yes! Each device can have its own attendance mode (Auto/Traditional) and duplicate prevention threshold. Perfect for organizations with different device locations or workflows.

**Q: Which ZKteco devices are supported?**
A: All ZKteco devices compatible with the pyzk library including uFace 202, uFace 800, ZK4500, K40, K50, and more. The module uses direct TCP/IP communication.

**Q: Can I use this without biometric devices?**
A: Yes, you can manually manage attendance records through Odoo's standard attendance interface. The module enhances both biometric and manual workflows.

**Q: Does this work with Odoo Community Edition?**
A: The module works with both Odoo 18 Community and Enterprise. However, some features like hr_contract integration work best with Enterprise.

**Q: Can I customize the penalty calculation?**
A: Yes, you can modify penalty rules in Settings → Attendance → Late Check-in. Supports both fixed amounts and per-minute calculations.

**Q: Is payroll integration mandatory?**
A: No, payroll integration is optional and only activates if hr_payroll_community module is installed.

**Q: How do I backup attendance data?**
A: Use Odoo's standard database backup, or export attendance reports regularly. Raw device data can also be extracted directly from devices.

**Q: Can I connect devices in different locations?**
A: Yes, as long as the devices are network-accessible from your Odoo server. VPN or cloud connectivity may be required for remote locations.

**Q: What happens if the device loses power?**
A: ZKteco devices have internal memory and battery backup. Attendance data is stored on the device until synced to Odoo.

**Q: Can I generate reports for multiple departments?**
A: Yes, reports support filtering by department, employee groups, or custom criteria.

**Q: Is there a mobile app?**
A: Currently no dedicated mobile app, but this is in our roadmap. The dashboard is mobile-responsive and works on tablets/phones.

---

## 🗺️ Roadmap

Future enhancements planned:

- 📱 **Mobile app integration** - Native Android/iOS apps for attendance
- 📍 **Geolocation-based attendance** - GPS tracking for field employees
- 🤖 **AI-powered insights** - Predictive analytics and pattern detection
- 🔔 **Advanced notification system** - Email/SMS alerts for issues
- 👤 **Employee self-service portal** - View own attendance, request corrections
- 🌍 **Multi-language support** - Translations for global deployment
- 📊 **Advanced analytics** - Machine learning for trend analysis
- ⏰ **Multi-shift support** - Better handling of shift workers
- 🎨 **Customizable dashboard** - Drag-and-drop dashboard widgets
- 🔗 **REST API** - External system integration via API

**Vote for features:** Contact us with your requirements!

---

## 🙏 Credits

**Developed by:** Rafiur Rahman Rafit
**Company:** Dot BD Solutions Limited
**Copyright:** © 2025 Dot BD Solutions Limited
**Website:** https://dotbd.com

### Third-Party Libraries
- **pyzk**: ZKteco device communication library
- **xlsxwriter**: Excel file generation
- **Chart.js**: Dashboard visualizations

---

## 📸 Screenshots

For screenshots and visual demonstrations, please visit:
- Module page on Odoo Apps Store
- Our website: https://dotbd.com
- Request a live demo: support@dotbd.com

---

**Thank you for choosing ZKteco HR Attendance Suite!**

For any questions, support requests, or custom development inquiries, please contact:

**Dot BD Solutions Limited**
📧 Email: support@dotbd.com
🌐 Website: https://dotbd.com
⏱️ Response Time: 24-48 hours

---

*Last updated: October 12, 2025 - Version 18.0.2.1.0*
