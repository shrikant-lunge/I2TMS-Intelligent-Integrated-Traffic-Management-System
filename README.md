# I²TMS — Intelligent Traffic & Transportation Management System

Nagpur Municipal Corporation (NMC) Intelligent Traffic & Transportation Management System. A web-based operations console designed for traffic operators and administrators to monitor live junctions, manage signal timing plans (Max-Pressure optimization & operator overrides), coordinate green corridors for emergency vehicles, track system incidents, and generate analytical reports.

## Key Modules & Features

- **Overview Dashboard (Screen 2)**: Visual summaries of active junctions, congestion indexes, and live video stream thumbnails.
- **Adaptive Signals (Screen 3 & 4)**: Real-time junction control displaying dynamic phase durations and queue lengths with manual timing overrides.
- **Decision Logs (Screen 5)**: Audited list of timing changes (system adaptive vs operator overrides) with paginated lookups.
- **Emergency Module (Screen 6, 7 & 8)**: Active dispatch forms for ambulances and fire trucks with preemption route mapping, ETA tracking, and upcoming VMS message coordinates.
- **Live Video (Screen 9)**: Live junction monitoring with split-panel CCTV feeds, digital recording controls, and camera snapshots.
- **Incidents & Alerts (Screen 10)**: Real-time list of system alarms, accidents, and breakdowns with 10s automatic polling and links to active emergency modules.
- **Analytical Reports (Screen 11)**: Dynamic query previews and PDF/CSV downloads for traffic, signal, congestion, and emergency reports.
- **System Settings (Screen 12)**: System-wide default variables, VMS board CRUD, operator user account creation/password resets, and system health status monitoring.

## Tech Stack

- **Backend**: Python 3, Flask, SQLAlchemy (SQLite database)
- **Frontend**: Vanilla HTML5, Vanilla CSS3 (custom CSS tokens), Javascript (ES6)
- **Libraries**:
  - `Leaflet.js`: Interactive routing and checkpoint maps
  - `Chart.js`: Analytics and historical dashboard graphs
  - `ReportLab`: Programmatic PDF report generation

---

## Setup & Installation

### 1. Clone & Navigate
```bash
git clone <repository-url>
cd ITMS_Final/i2tms
```

### 2. Set Up Virtual Environment
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Mac/Linux:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy the template `.env.example` file to `.env`:
```bash
copy .env.example .env      # Windows
cp .env.example .env        # Mac/Linux
```
Open `.env` and fill in the secrets:
- `SECRET_KEY`: Random string for encrypting user sessions.
- `ADMIN_SEED_PASSWORD`: Password for the default administrator account.
- `DATABASE_URL`: Location of the SQLite database.

### 5. Run the Server
```bash
python app.py
```
Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

---

## Administrator Credentials

You will need to add administrator details to the database file (`database/i2tms.db`) inside the `users` table. You can use any SQLite client (such as DB Browser for SQLite) or use standard SQL commands to insert accounts, ensuring the password hash is correctly generated using `werkzeug.security`.

---

## Mock Hand-offs & YOLOv8 Pipeline Notes

This application contains placeholder elements designed to be swapped with the automated detection pipeline built by other team members:
1. **Camera Feeds (Screen 9)**: served from static image thumbnails. Real integration should hook RTSP stream sources to the video tag.
2. **Junction Detection Data**: PCU volumes, queue lengths, and speeds are seeded or generated dynamically. Once the YOLOv8 vehicle detection pipeline is operational, its aggregated endpoints should overwrite these data dictionaries in `app.py`.
3. **AI Health Indicator (Screen 12)**: The AI health check in the settings footer is mocked as "Online". This can be connected to check the status of the YOLOv8 pipeline container.
