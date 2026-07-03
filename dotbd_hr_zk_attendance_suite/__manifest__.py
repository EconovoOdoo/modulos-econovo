# -*- coding: utf-8 -*-
################################################################################
#
#    Dot BD Solutions Limited
#    Copyright (C) 2025-TODAY Dot BD Solutions Limited
#    Author: Rafiur Rahman Rafit
#

#
################################################################################
{
    'name': 'ZKteco Biometric HR Attendance Suite and Payroll',
    'version': '17.0.5.0.2',
    'category': 'Human Resources/Attendance',
    'sequence': 10,
    'summary': "Complete HR Attendance Solution with ZKteco Biometric Integration, "
               "ADMS Cloud Push Protocol, Real-time Live Capture, "
               "Device Health Monitoring, LCD Messages, "
               "Door Control & Hybrid Connection Mode (PyZK + ADMS)",
    'description': """
ZKteco HR Attendance Management Suite
======================================

The most comprehensive attendance management solution for Odoo 17, featuring seamless
ZKteco biometric device integration, powerful analytics dashboard, intelligent anomaly
detection, and enterprise-grade reporting capabilities.

🔐 Advanced Biometric Integration (100% PyZK Implementation)
-----------------------------------
• **Multi-Device Support**: Connect unlimited ZKteco devices (uFace 202, uFace 800, ZK4500, K40, etc.)
• **Face & Fingerprint Recognition**: Support for all ZKteco biometric authentication methods
• **Real-Time Live Capture (NEW!)**: Instant attendance capture as events happen - no more polling delays!
• **Auto Check-in/Check-out Mode**: Intelligent mode that automatically determines check-in/check-out,
  ignoring device punch type - prevents HR configuration mistakes!
• **Duplicate Punch Prevention**: Automatically ignores repeated punches within configurable time window (default: 5 seconds)
• **Device Health Monitoring (NEW!)**: Track firmware, capacity, storage, network info
• **Automatic User Enrollment (NEW!)**: Sync employees from Odoo to device with one click
• **LCD Message Display (NEW!)**: Personalized welcome/goodbye messages on device screen
• **Audio Feedback (NEW!)**: Custom sounds for check-in, check-out, and errors (55+ voices)
• **Door Access Control (NEW!)**: Unlock doors remotely with configurable duration
• **Traditional Mode**: Classic mode using device punch type for backward compatibility
• **Automatic Sync**: Real-time attendance data synchronization with configurable intervals
• **Device Management**: Centralized control panel for managing multiple devices
• **Attendance Validation**: Automatic check-in/check-out detection with intelligent pairing
• **Employee Mapping**: Auto-link device users with Odoo employees

📊 Real-time Analytics Dashboard
----------------------------------
• **Interactive Visualizations**: Beautiful charts with Chart.js integration
• **Smart Filters**: Pre-configured date ranges (Today/Week/Month/Year/Custom)
• **Live Statistics**: Real-time attendance metrics and KPIs
• **Anomaly Alerts**: Instant detection of attendance issues
• **Department Analytics**: Filter by department, employee, or custom criteria
• **Export Capabilities**: Download dashboard data for further analysis

🔍 Intelligent Anomaly Detection
----------------------------------
• **Missing Check-in/Check-out**: Automatic detection of incomplete attendance records
• **Duplicate Punch Detection**: Identify and flag duplicate biometric punches
• **Attendance Violations**: Track policy violations and unusual patterns
• **Automated Categorization**: Smart classification of different anomaly types
• **Anomaly Reports**: Dedicated reports for compliance and audit purposes
• **Issue Resolution Workflow**: Built-in approval process for handling anomalies

⏰ Late Check-in Management System
------------------------------------
• **Configurable Tolerance**: Set grace periods (e.g., 5 minutes) before marking late
• **Automatic Penalty Calculation**: Define penalty amounts per minute/instance
• **Approval Workflow**: Four-state system (Draft/Approved/Refused/Deducted)
• **Payroll Integration**: Seamless connection with hr_payroll_community module
• **Late Analytics Dashboard**: Track late trends and patterns by employee/department
• **Email Notifications**: Automatic alerts for late arrivals (optional)
• **Penalty Waiver System**: Allow managers to approve/refuse penalties

📅 Professional Attendance Sheets
-----------------------------------
• **Calendar-Style Layout**: Excel-like monthly attendance sheets
• **Color-Coded Status**: Visual indicators for Present/Absent/Late/Leave/Weekend/Holidays
• **Multiple Export Formats**: Generate PDF and Excel reports
• **Combined or Individual**: Choose between company-wide or per-employee sheets
• **Rich Statistics**: Work hours, late minutes, attendance rates, and rankings
• **Department Filtering**: Generate reports by department or employee groups
• **Time Off Integration**: Automatic display of approved leaves and public holidays

📈 Comprehensive Reporting Suite
----------------------------------
• **Summary Reports**: Aggregated attendance statistics by employee/period
• **Detailed Daily Reports**: Complete day-by-day breakdown with check-in/out times
• **Late Check-in Reports**: Comprehensive penalty tracking with employee summaries
• **Anomaly Reports**: Dedicated reports for attendance issues and violations
• **Excel Export**: Professional XLSX reports with formatting and charts
• **PDF Generation**: Print-ready reports with company branding
• **Custom Date Ranges**: Flexible filtering for any time period
• **Department Analytics**: Group reports by organizational structure

🎯 Enterprise Features
-----------------------
• **Time Off Integration**: Seamless connection with Odoo Leave Management (hr_holidays)
• **Public Holidays**: Automatic detection and display of company-wide holidays
• **Working Calendar**: Respect employee working schedules and shifts
• **Overtime Tracking**: Calculate overtime and undertime hours automatically
• **Multi-Company Support**: Works with multiple companies in same database
• **Access Control**: Role-based permissions for HR managers and employees
• **Audit Trail**: Complete history of attendance modifications
• **Data Security**: Enterprise-grade security and data protection

💼 Payroll Integration (Optional)
-----------------------------------
• **Automatic Deductions**: Late penalties automatically added to payslips
• **Salary Rule**: Pre-configured deduction rule for late check-ins
• **Payslip Line Items**: Transparent display of penalty deductions
• **Integration with hr_payroll_community**: Seamless connection with community payroll module

🛠️ Technical Features
-----------------------
• **pyzk Library**: Direct device communication without third-party APIs
• **RESTful API**: Optional external API for mobile apps and integrations
• **Scheduled Actions**: Automatic sync via Odoo cron jobs
• **SQL Views**: High-performance database views for analytics
• **Optimized Queries**: Fast performance even with large datasets
• **Modular Architecture**: Clean code structure for easy customization
• **Python 3.10+ Compatible**: Latest Python standards

✅ Perfect For
---------------
• Companies using ZKteco biometric devices for attendance
• HR departments managing attendance policies and penalties
• Organizations requiring comprehensive attendance analytics
• Businesses needing compliance and audit reporting
• Companies with strict late arrival policies
• Multi-location enterprises with distributed workforce

📦 What's Included
-------------------
• Full source code with OPL-1 license
• Comprehensive documentation (README.md)
• Installation guide and setup instructions
• Sample data for testing
• 90 days of support and updates
• Free bug fixes and security patches

🔄 Version History
-------------------
• v17.0.5.0.0 - Full feature port from v18: payroll suite, device logs, wizards, map, dashboards
• v17.0.2.3.0 - Previous v17 release

🌐 Support & Documentation
----------------------------
• Email: support@dotbd.com
• Website: https://dotbd.com
• Documentation: Included in module
• Response Time: 24-48 hours

⚠️ Requirements
----------------
• Odoo 17.0 (Community or Enterprise)
• Python packages: pyzk, xlsxwriter
• Optional: hr_payroll_community (for payroll integration)

🔧 Quick Setup Guide
--------------------
1. Install the module
2. Go to Attendance → Biometric Device
3. Add your ZKteco device (IP, Port)
4. Test connection (recommended on local network first)
5. Configure working schedules
6. Link employees with ZK User IDs
7. Set attendance rules and tolerances
8. Start tracking attendance!

📱 Menu Navigation
------------------
• Attendance → Biometric Device: Add and manage devices
• Attendance → Overview: View attendance records
• Attendance → Settings: Configure rules and tolerances
• Attendance → Dashboard: View analytics and reports
• Attendance → Generate Report: Create custom reports
• Attendance → Anomaly Analysis: Track attendance issues
    """,
    'author': 'Dot BD Solutions Limited',
    'company': 'Dot BD Solutions Limited',
    'maintainer': 'Rafiur Rahman Rafit',
    'website': "https://dotbdsolutions.com",
    'support': 'info@dotbdsolutions.com',

    # Pricing Information (Odoo Apps Store)
    'price': 89.00,
    'currency': 'USD',

    # Technical Information
    'depends': ['base_setup', 'hr_attendance', 'hr_holidays'],
    # NOTE: the ZKTeco library (pyzk → imports as 'zk', or its fork pyzk2 →
    # imports as 'pyzk2') is OPTIONAL and intentionally NOT listed here.
    # Odoo's external_dependencies check uses the IMPORT name, and the two libs
    # import under different names, so hard-listing either would block install
    # for users who have the other. The code imports both with a graceful
    # fallback (direct-TCP PyZK features simply disable if neither is present;
    # ADMS push always works). Install one of: `pip install pyzk2` (recommended)
    # or `pip install pyzk`.
    'external_dependencies': {
        'python': ['xlsxwriter'],
    },

    # Assets (CSS, JS)
    'assets': {
        'web.assets_backend': [
            'dotbd_hr_zk_attendance_suite/static/src/css/list_view_scroll_fix.css',
            'dotbd_hr_zk_attendance_suite/static/src/components/attendance_dashboard/attendance_dashboard.scss',
            'dotbd_hr_zk_attendance_suite/static/src/components/attendance_dashboard/attendance_dashboard.xml',
            'dotbd_hr_zk_attendance_suite/static/src/components/attendance_dashboard/attendance_dashboard.js',
            'dotbd_hr_zk_attendance_suite/static/src/components/payroll_dashboard/payroll_dashboard.scss',
            'dotbd_hr_zk_attendance_suite/static/src/components/payroll_dashboard/payroll_dashboard.xml',
            'dotbd_hr_zk_attendance_suite/static/src/components/payroll_dashboard/payroll_dashboard.js',
        ],
    },

    # Data Files
    'data': [
        'security/attendance_security.xml',
        'security/ir.model.access.csv',
        'data/ir_cron_biometric.xml',
        'data/late_check_in_data.xml',
        'data/hr_leave_type_default_codes.xml',
        'wizard/biometric_template_wizard_view.xml',
        'wizard/bulk_template_wizard_view.xml',
        'wizard/adms_template_wizard_views.xml',
        'wizard/attendance_download_wizard_views.xml',
        'wizard/batch_pdf_generation_wizard_views.xml',
        'wizard/zk_import_users_wizard_views.xml',
        'views/biometric_device_details_views.xml',
        'views/biometric_device_log_views.xml',
        'views/biometric_log_cleanup_wizard_views.xml',
        'views/zk_machine_attendance_views.xml',
        'views/hr_employee_views.xml',
        'views/res_users_views.xml',
        'views/hr_leave_type_views.xml',
        'views/hr_attendance_views.xml',
        'views/daily_attendance_views.xml',
        'views/attendance_anomaly_analysis_views.xml',
        'views/device_map_views.xml',
        'views/attendance_map_views.xml',
        'views/biometric_device_attendance_menus.xml',
        'views/attendance_report_wizard_views.xml',
        'views/late_check_in_views.xml',
        'views/res_config_settings_views.xml',
        'views/templates/device_map_template.xml',
        'views/templates/attendance_anomaly_dashboard.xml',
        'views/attendance_anomaly_dashboard_menu.xml',
        'views/employee_attendance_sheet_wizard_views.xml',
        'views/templates/employee_attendance_sheet_report.xml',
        'views/adms_device_command_views.xml',
        'views/attendance_main_dashboard_views.xml',
        # Monthly Employee Statement (Attendance + Financial Summary PDF)
        'views/dotbd_monthly_statement_views.xml',
        'views/templates/dotbd_monthly_statement_pdf_template.xml',
        # Payroll — Festive bonus seed data
        'data/dotbd_festive_bonus_data.xml',
        # Payroll — Phase 1: salary templates + assignments
        'data/dotbd_payroll_data.xml',
        'data/dotbd_bd_salary_templates.xml',
        'data/dotbd_intl_salary_templates.xml',
        'views/dotbd_salary_template_views.xml',
        'views/dotbd_employee_salary_views.xml',
        # Payroll — Phase 2: payslip engine
        'views/dotbd_payslip_views.xml',
        'views/dotbd_payslip_wizard_views.xml',
        'views/templates/dotbd_payslip_pdf_template.xml',
        # Payroll — Phase 3-6: email template + contract wizard
        'data/dotbd_payslip_email_template.xml',
        'views/dotbd_contract_wizard_views.xml',
        # Payroll — Dashboard
        'views/dotbd_payroll_dashboard_views.xml',
        # Payroll — Festive bonus views
        'views/dotbd_festive_bonus_views.xml',
        # Payroll — Salary Certificate
        'data/dotbd_salary_certificate_sequence.xml',
        'views/dotbd_salary_certificate_views.xml',
        'views/templates/dotbd_salary_certificate_pdf_template.xml',
        # Payroll — Menus (must come after all actions)
        'views/dotbd_payroll_menus.xml',
        # Attendance Statement — native payroll bridge (Community & Enterprise)
        'views/dotbd_attendance_statement_views.xml',
    ],

    # Payroll integration: loaded conditionally via post_init_hook if hr_payroll_community is installed
    'post_init_hook': 'post_init_hook',

    # Images and Screenshots
    'images': [
        'static/description/banner.png',
        'static/description/device_hybrid_mode.png',
        'static/description/device_hybrid_warning.png',
        'static/description/device_config_tabs.png',
        'static/description/device_overview_full.png',
        'static/description/icon.png',
        'static/description/dotbd_solutions_logo.png',
        'static/description/img.png',
        'static/description/screenshot/img_2.png',
        'static/description/screenshot/img_3.png',
        'static/description/screenshot/img_4.png',
        'static/description/screenshot/img_5.png',
        'static/description/screenshot/img_6.png',
        'static/description/screenshot/img_7.png',
        'static/description/screenshot/img_8.png',
        'static/description/screenshot/img_9.png',
        'static/description/screenshot/img_10.png',
        'static/description/screenshot/img_11.png',
        'static/description/screenshot/img_12.png',
        'static/description/screenshot/img_13.png',
        'static/description/screenshot/img_14.png',
        'static/description/screenshot/img_15.png',
        'static/description/screenshot/img_16.png',
        'static/description/screenshot/img_17.png',
        'static/description/screenshot/img_18.png',
        'static/description/screenshot/img_19.png',
        'static/description/screenshot/img_20.png',
        'static/description/screenshot/img_21.png',
        'static/description/screenshot/img_22.png',
        'static/description/screenshot/img_23.png',
        'static/description/screenshot/img_24.png',
        'static/description/screenshot/img_25.png',
        'static/description/screenshot/img_26.png',
        'static/description/screenshot/img_27.png',
        'static/description/screenshot/img_28.png',
        'static/description/screenshot/img_29.png',
        'static/description/screenshot/img_30.png',
        'static/description/screenshot/img_31.png',
        'static/description/screenshot/img_32.png',
        'static/description/screenshot/img_33.png',
        'static/description/screenshot/img_34.png',
        'static/description/screenshot/img_35.png',
        'static/description/screenshot/Screenshot from 2025-11-12 12-30-01.png',
        'static/description/screenshot/Screenshot from 2025-11-12 12-30-20.png',
        'static/description/screenshot/Screenshot from 2025-11-12 12-30-34.png',
        'static/description/screenshot/Screenshot from 2025-11-12 12-31-02.png',
        'static/description/screenshot/Screenshot from 2025-11-12 12-31-10.png',
        'static/description/screenshot/Screenshot from 2025-11-12 12-31-15.png',
        'static/description/screenshot/Screenshot from 2025-11-12 12-31-31.png',
        'static/description/screenshot/Screenshot from 2025-11-12 12-32-06.png',
        'static/description/screenshot/Screenshot from 2025-11-12 12-32-56.png',
    ],

    # Tags for Odoo Apps Store
    'tags': [
        'attendance', 'biometric', 'zkteco', 'hr', 'human resources',
        'adms', 'cloud attendance', 'push protocol', 'real-time sync',
        'no middleware', 'pyzk', 'live capture',
        'zk teco', 'zk-teco', 'zkteco device', 'zkteco attendance',
        'zkteco biometric', 'zkteco integration', 'zkteco odoo',
        'zkteco uface 202', 'uface 202', 'zkteco uface 302', 'uface 302',
        'zkteco uface 402', 'uface 402', 'zkteco uface 602', 'uface 602',
        'zkteco uface 800', 'uface 800', 'zkteco speedface', 'speedface',
        'zkteco speedface v5l', 'speedface v5l', 'zkteco speedface h5', 'speedface h5',
        'zkteco speedface m4', 'speedface m4', 'zkteco proface x', 'proface x',
        'zkteco proface plus', 'proface plus', 'zkteco vf300', 'vf300',
        'zkteco vf350', 'vf350', 'zkteco vf380', 'vf380',
        'zkteco facepass 7', 'facepass 7', 'zkteco multibio 700', 'multibio 700',
        'zkteco multibio 800', 'multibio 800',
        'zkteco f18', 'f18', 'zkteco f16', 'f16', 'zkteco f19', 'f19',
        'zkteco f21', 'f21', 'zkteco f22', 'f22',
        'zkteco k14', 'k14', 'zkteco k20', 'k20', 'zkteco k28', 'k28',
        'zkteco k30', 'k30', 'zkteco k40', 'k40', 'zkteco k40 pro', 'k40 pro',
        'zkteco k50', 'k50', 'zkteco k60', 'k60',
        'zkteco mb10', 'mb10', 'zkteco mb10vl', 'mb10vl',
        'zkteco mb20', 'mb20', 'zkteco mb160', 'mb160',
        'zkteco mb200', 'mb200', 'zkteco mb360', 'mb360',
        'zkteco mb460', 'mb460', 'zkteco mb560', 'mb560',
        'zkteco mb860', 'mb860', 'zkteco ma300', 'ma300',
        'zkteco ma500', 'ma500', 'zkteco zk9500', 'zk9500',
        'zkteco zk4500', 'zk4500',
        'zkteco iclock 260', 'iclock 260', 'zkteco iclock 360', 'iclock 360',
        'zkteco iclock 560', 'iclock 560', 'zkteco iclock 680', 'iclock 680',
        'zkteco iclock 700', 'iclock 700', 'zkteco iclock 880', 'iclock 880',
        'zkteco iclock 990', 'iclock 990', 'zkteco iclock 9000', 'iclock 9000',
        'zkteco ua100', 'ua100', 'zkteco ua200', 'ua200',
        'zkteco ua300', 'ua300', 'zkteco ua400', 'ua400',
        'zkteco ua760', 'ua760', 'zkteco ua860', 'ua860',
        'zkteco u100', 'u100', 'zkteco u160', 'u160',
        'zkteco u300', 'u300', 'zkteco u350', 'u350',
        'zkteco u650', 'u650', 'zkteco x628', 'x628',
        'zkteco x638', 'x638', 'zkteco x990', 'x990',
        'zkteco g1', 'g1', 'zkteco g2', 'g2',
        'zkteco g3', 'g3', 'zkteco g4', 'g4',
        'zkteco silkfp', 'silkfp', 'zkteco silkid', 'silkid',
        'zkteco in01', 'in01',
        'zkteco c3-100', 'c3-100', 'zkteco c3-200', 'c3-200',
        'zkteco c3-400', 'c3-400', 'zkteco inbio160', 'inbio160',
        'zkteco inbio260', 'inbio260', 'zkteco inbio460', 'inbio460',
        'late penalty', 'overtime calculation', 'anomaly detection',
        'door control', 'access control', 'hr dashboard', 'analytics',
        'attendance report', 'excel export', 'pdf report',
        'attendance tracking', 'employee attendance', 'time tracking',
        'shift management', 'leave management', 'payroll integration',
        'bangladesh', 'dubai', 'uae', 'gcc', 'asia', 'fingerprint scanner',
        'face recognition', 'biometric attendance', 'tcp/ip', 'standalone sdk',
        'zk time', 'zktime.net', 'attendance machine', 'punch machine',
    ],

    # Classification
    'license': 'OPL-1',
    'installable': True,
    'auto_install': False,
    'application': True,
    'web': True,

    # Pre-installation hook to clean up old views BEFORE XML loading
    'pre_init_hook': 'pre_init_hook',
}
