# Gemini Updates — Monthly Work Tracking & Compliance Reporting Portal

**Gemini Updates** is a production-ready internal work-tracking and compliance-reporting portal built using Python and Django. The system provides role-based access for **Boss** and **Employee** users, features a dynamic monthly daily report matrix, automates 15 monthly compliance items across 5 companies, tracks detailed audit histories, and offers persistent Light and Dark theme switching.

---

## Key Features

### 1. Role-Based Access Control
- **Boss Role**:
  - View and manage all employee daily report entries.
  - Leave comments on any employee's daily task entry or compliance item.
  - Access **Employee Management** to add employees, edit profiles, activate/deactivate accounts, promote employees to Boss, or demote a Boss to Employee (with demotion protection ensuring at least 1 Boss remains active).
  - View full **Activity / Audit Logs** with multi-field search and filters.
  - Access **Missing Daily Reports** view to identify unsubmitted employee reports for specific dates.
- **Employee Role**:
  - View the **Daily Report** matrix in read-only mode for other employees; create/edit strictly their own task entries.
  - View the **Compliance Report** matrix and mark any `PENDING` compliance item as `DONE` (single completion rule enforced with database-level `select_for_update` row locking).
  - View Boss feedback comments attached to daily tasks and compliance items.

### 2. Daily Report Module
- Tabular monthly structure dynamically rendering day columns based on the selected month (1 to 28/29/30/31), correctly handling leap years via `calendar.monthrange`.
- Sticky employee column and table headers for horizontal scrolling.
- Status indicators: Completed (Green), In Progress (Blue/Info), Blocked (Red/Warning), Not Started (Gray), with comment indicator dots when Boss comments exist.

### 3. Compliance Report Module
- Auto-generated compliance records per month (5 Companies: `GI`, `International`, `HUF`, `LLP`, `GTW` × Compliance Types: `TDS Payment`, `GSTR-1`, `GSTR-3B`, and Quarterly TDS Returns).
- Immutable `DONE` state with timestamp, completing user, reference/challan number, remarks, and document link.
- Export options: Export monthly matrix to **CSV** and **Excel (.xlsx)** format.
- Print-friendly layout view.

### 4. Role-Tailored Dashboard
- **Boss Dashboard**: Active employee counts, today's report submission rate, monthly compliance summary cards, recent audit feed, and quick control links.
- **Employee Dashboard**: Own monthly report completion %, today's submission status, compliance summary, recent compliance updates, and Boss feedback comments.

### 5. Theme Switching Engine
- Persistent Light and Dark mode toggle built into top navigation bar.
- Uses `localStorage` and system `prefers-color-scheme` preferences.

---

## Setup & Running Instructions

### 1. Prerequisites
- Python 3.10+
- Django 5.0+

### 2. Installation
Clone the repository and install dependencies:
```bash
python -m pip install -r requirements.txt
```

### 3. Database Setup & Seeding
Run database migrations and populate default seed data:
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py seed_data
```

### 4. Run Development Server
```bash
python manage.py runserver
```
Navigate to `http://127.0.0.1:8000/` in your web browser.

---

## Pre-Configured Demo Accounts

| Role | Username | Email | Password |
| :--- | :--- | :--- | :--- |
| **Boss** | `boss` | `boss@gemini.com` | `boss123` |
| **Employee 1** | `emp1` | `emp1@gemini.com` | `emp123` |
| **Employee 2** | `emp2` | `emp2@gemini.com` | `emp123` |
| **Employee 3** | `emp3` | `emp3@gemini.com` | `emp123` |

---

## Automated Test Suite
To run all permissions, concurrency, and workflow unit tests:
```bash
python manage.py test
```

---

## Project Structure
```
gemini_updates/
├── accounts/         # User model, auth views, employee management, decorators, unit tests
├── reports/          # Daily task report matrix, modal views, comments, missing reports filter
├── compliance/       # Compliance matrix (5x3), single completion, exports (CSV/Excel), print view
├── audit/            # AuditLog model, log_action helper, searchable audit trail view
├── dashboard/        # Role-tailored dashboard views and metrics
├── templates/        # Responsive HTML5 base template, navbar, modals, error pages (403, 404, 500)
├── static/           # CSS design system (theme.css), JavaScript theme toggle & modal engine (theme.js)
├── manage.py
└── requirements.txt
```
