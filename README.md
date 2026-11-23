# HostelX – Smart Hostel Room Exchange and Hostel Management Platform

**HostelX** is a centralized university hostel management, direct room booking, and cyclic room exchange web application built with Django, SQLite, Bootstrap 5, NetworkX, and Chart.js.

It provides a comprehensive solution for university hostel operations: **direct room booking** for new/existing students, **peer-to-peer room exchanges** (direct and multi-party cycles of 3, 4, or 5 students), a **master admin control hub**, and full hostel services (Mess, Laundry, Maintenance).

---

## Key Features

1. **Direct Hostel Room Booking Facility (`/rooms/book/`):**
   - **Browse Vacant Beds:** Real-time catalog of all vacant beds across campus filtered by gender, hostel, room category, floor, and AC/non-AC status.
   - **One-Click Direct Allotment:** Select a bed, review annual room pricing, apply available advance balances, and confirm with simulated payment.
   - **Instant Atomic Allotment:** Bed status updates to `OCCUPIED`, active `BedAllocation` created, mess registration established, financial ledger debited, and official **Allotment Order Certificate** issued.
   - **Seamless Transfers:** If an allocated student books a new bed, their old bed is safely released back to `VACANT` without occupancy conflicts.

2. **Authentication & Student Registration System (`/accounts/`):**
   - **New Student Registration (`/accounts/register/`):** Sign up with username, password, full name, email, phone, gender, course, department, and academic year.
   - **Instant Portal Access:** Automatically initializes student profile and financial account, logs the user in, and directs them to book a room.
   - **Sign In / Log In (`/accounts/login/`):** Authenticate with existing credentials or use one-click demo role fillers.

3. **Master Admin Control Hub (`/admin-panel/`):**
   - **Control All Stuff in One Place:**
     - **Rooms & Bed Inventory (`/admin-panel/rooms/`):** Add new rooms, specify categories & floor, auto-generate beds, and toggle bed availability statuses (`Vacant`, `Occupied`, `Blocked`, `Maintenance`) with live dropdowns.
     - **Direct Bookings Manager (`/admin-panel/bookings/`):** Review all room booking orders, view printable certificates, and use the **Direct Manual Allotment Tool** to allocate any student to any bed.
     - **Students Controller (`/admin-panel/students/`):** Search students, toggle fee payment statuses (`PAID`/`PARTIAL`/`UNPAID`), toggle disciplinary holds (`CLEAN`/`HOLD`), suspend accounts, or de-allocate beds.
     - **Policies & Pricing (`/dashboard/admin/`):** Configure exchange rules, cycle bounds (2-5), administrative processing fees, cooling-off periods, and annual pricing schedules.

4. **Smart Room Exchange & Cyclic Matching Engine (`/exchanges/`):**
   - **Direct 2-Student Swaps:** Peer-to-peer bed exchange with mutual agreement.
   - **Multi-Party Cycles (3 to 5 Students):** NetworkX-powered directed graph cycle detection allowing 3, 4, or 5 students to rotate beds mutually.
   - **Strict Validation:** Same-gender restriction, active student status, clear disciplinary records, fee clearance, cooling-off period, and conflict checks.
   - **Roommates Unaffected:** Only participating students swap; non-participating occupants remain in their original beds.

5. **Approval & Financial Workflows:**
   - **All-Participant Acceptance:** If any participant declines, the proposal is rejected with zero partial impact.
   - **Warden Approvals:** Same-hostel exchanges require 1 warden; cross-hostel exchanges require approvals from all involved hostel wardens.
   - **Annual Fee Calculations:** Automatic calculation of annual room fee differences. Moving to a cheaper room generates an **advance balance** for the next academic year (no cash refund).
   - **Processing Fee:** Configurable administrative processing fee (₹200) charged individually to each participant.
   - **Official PDF Transfer Letters:** Downloadable university transfer certificates generated using ReportLab.

6. **Hostel Services:**
   - **Mess Management:** 7-day 4-meal weekly menus (Breakfast, Lunch, Snacks, Dinner), dietary preference selection (Veg, Non-Veg, Jain), and student dining feedback.
   - **Laundry Management:** Catalog, pickup slot bookings, weight-based pricing, and status tracking (Requested &rarr; Delivered).
   - **Maintenance Helpdesk:** Ticket reporting for Electrical, Plumbing, AC, Furniture, Wi-Fi, Housekeeping with priority and photo uploads.
   - **Campus Facilities:** Central Library, Fitness Suite, Sports Arenas, Wi-Fi mesh, Health & Wellness center.

7. **5 Role-Specific Dashboards:**
   - **Student:** Allotment card, annual fee, advance balance, proposals, direct room booking, requests, mess & service widgets.
   - **Hostel Warden:** Occupancy stats, interactive real-time floor bed visualizer grid, pending approvals, resident directory.
   - **Chief Warden:** Cross-hostel overview, active proposal monitoring, escalation actions, and matching engine.
   - **University Administrator:** Control hub for rooms, direct bookings, students, pricing, and policies.
   - **Dean of Student Welfare:** Executive read-only analytics with Chart.js charts.

---

## Local Development Setup

### 1. Requirements
- Python 3.12+ (Tested on Python 3.14)
- PostgreSQL 14+ (or SQLite 3 via `USE_SQLITE=True`)

### 2. Installation
Clone or navigate to the project directory:
```bash
cd hostal-booking
```

Install dependencies:
```bash
pip install -r requirements.txt
```

### 3. Database Setup & Initialization (PostgreSQL)

1. **Create the PostgreSQL Database:**
   ```sql
   CREATE DATABASE hostel_db;
   ```

2. **Configure `.env`:**
   Copy `.env.example` to `.env` and verify your credentials:
   ```env
   DATABASE_ENGINE=django.db.backends.postgresql
   DATABASE_NAME=hostel_db
   DATABASE_USER=postgres
   DATABASE_PASSWORD=your_password
   DATABASE_HOST=localhost
   DATABASE_PORT=5432
   ```

3. **Apply Migrations:**
   ```bash
   python manage.py migrate
   ```

4. **Seed Database or Restore Existing Data:**
   - **Option A (Seed fresh university data):**
     ```bash
     python manage.py seed_hostel_data
     ```
     *This seeds 1 University, 4 Hostels, 6 Categories, 120 Rooms, 348 Beds, 318 Fictional Students, 4 Wardens, Chief Warden, Dean, Admin, Mess Menus, and Services.*
   
   - **Option B (Restore data dumped from previous database):**
     ```bash
     python manage.py loaddata datadump.json
     ```

### 4. Run the Development Server
```bash
python manage.py runserver
```
Open your browser and navigate to:
```
http://127.0.0.1:8000/
```

---

## Demo Accounts

All demo accounts use password: **`HostelX@2026`**  
*(The login page at `/accounts/login/` features 1-click demo credential fillers for instant testing).*

| Role | Username / Reg No | Full Name / Description | Allotted Bed / Scope |
|---|---|---|---|
| **Day Scholar Student** | `12313714` | Aarav Sharma | Day Scholar (Off-Campus, tests direct Hostel Room Booking) |
| **Day Scholar Student** | `12313715` | Rohan Gupta | Day Scholar (3rd Year Mechanical) |
| **Student (Male)** | `student_rahul` | Rahul Sharma | H001-101-B1 (Boys Hostel A, AC Single) |
| **Student (Male)** | `student_amit` | Amit Verma | H001-102-B1 (Boys Hostel A, AC Double) |
| **Student (Male)** | `student_vikram` | Vikram Rao | H002-101-B1 (Boys Hostel B, AC Single) |
| **Student (Female)** | `student_priya` | Priya Nair | H003-101-B1 (Girls Hostel A, AC Single) |
| **Student (Female)** | `student_ananya` | Ananya Sen | H004-101-B1 (Girls Hostel B, AC Single) |
| **Student (Unpaid Fee)** | `student_unpaid` | Aditya Singh | Fee status UNPAID (tests eligibility rejection) |
| **Student (Disciplinary)** | `student_hold` | Manish Gupta | HOLD status (tests disciplinary rejection) |
| **Hostel Warden** | `warden_ha` | Dr. Suresh Verma | Assigned to Boys Hostel A (H001) |
| **Hostel Warden** | `warden_ga` | Dr. Sunita Deshmukh | Assigned to Girls Hostel A (H003) |
| **Chief Warden** | `chief_warden` | Dr. Rajesh Sharma | Cross-hostel executive console |
| **University Admin** | `admin` | Administrator | Full master control hub (`/admin-panel/`) |
| **Dean** | `dean` | Prof. Meenakshi Sundaram | Read-only executive reports & Chart.js charts |

---

## Running Automated Tests

Run the full automated test suite (20 tests covering authentication, registration, direct room booking, cyclic matching, fee calculations, atomic transactions, and admin controls):
```bash
python manage.py test
```
*(All 20 test suites pass cleanly in `< 4.0` seconds on the SQLite database).*
