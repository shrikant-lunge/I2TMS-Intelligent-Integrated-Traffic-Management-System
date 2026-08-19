# I²TMS — Intelligent Integrated Traffic Management System

An intelligent traffic management solution designed to optimize urban traffic flow and create a dynamic emergency corridor using real-time vehicle detection, adaptive signal timing, route intelligence, and centralized monitoring.

![Status](https://img.shields.io/badge/status-prototype-orange)
![License](https://img.shields.io/badge/license-Educational%20Use-blue)
![Python](https://img.shields.io/badge/python-3.9%2B-blue?logo=python&logoColor=white)
![JavaScript & CSS](https://img.shields.io/badge/frontend-React-61DAFB?logo=react&logoColor=white)
![YOLO](https://img.shields.io/badge/vision-YOLO-black)
![OSRM](https://img.shields.io/badge/routing-OSRM-brightgreen)

**Contents**
- [Overview](#overview)
- [Key Features](#key-features)
- [How It Works](#how-it-works)
- [Dynamic Signal Timing](#dynamic-signal-timing)
- [Green Corridor Logic](#green-corridor-logic)
- [Computer Vision](#computer-vision)
- [Emergency Vehicle Tracking](#emergency-vehicle-tracking)
- [ANPR Integration](#anpr-integration)
- [System Architecture](#system-architecture)
- [Technology Stack](#technology-stack)
- [Problem Statement](#problem-statement)
- [Use Cases](#use-cases)
- [Getting Started](#getting-started)
- [Future Scope](#future-scope)
- [Project Status](#project-status)
- [Contributing](#contributing)
- [Team](#team)
- [Technical Reference](#technical-reference)
- [Acknowledgements](#acknowledgements)
- [License](#license)

---

## Overview

I²TMS (Intelligent Integrated Traffic Management System) is a smart transportation prototype designed to address real-world urban traffic challenges such as congestion, inefficient signal timing, and delays faced by emergency vehicles.

The system combines computer vision, traffic engineering, route calculation, GPS tracking, ANPR, VMS coordination, and adaptive traffic control into a unified software platform.

The system consists of three core modules:

| Module | Purpose |
|---|---|
| Dynamic Signal Timing | Allocates signal green-time in real time based on live traffic conditions |
| Green Corridor | Creates and manages a clear route for emergency vehicles such as ambulances and fire trucks |
| Dashboard | Provides centralized traffic analytics and control capabilities |

---

## Key Features

### Dynamic Signal Timing

Traditional traffic signals often operate using fixed timings regardless of current traffic demand. I²TMS uses Webster's Signal Timing Formula and continuously updated traffic data to dynamically determine signal timings.

The system:

- Detects vehicles from camera footage using YOLO
- Calculates traffic demand for each approach
- Converts different vehicle types into Passenger Car Units (PCU)
- Recalculates signal timing using live traffic information
- Allocates green time proportionally to traffic demand
- Applies minimum and maximum green-time constraints to prevent starvation and excessive waiting

### Green Corridor

The Green Corridor module helps emergency vehicles move through congested routes more efficiently.

The workflow includes:

- Destination selection by the emergency vehicle
- Fastest-route calculation using OSRM
- GPS-based emergency vehicle tracking
- Automatic emergency activation
- Coordination of traffic signals along the route
- Coordination of Variable Message Signs (VMS)
- ANPR-based identification of vehicles blocking an active emergency corridor

### Route-Based Infrastructure Coordination

Instead of relying only on raw GPS-radius checks, I²TMS uses distance along the calculated route.

The system:

1. Loads predefined junction and VMS locations
2. Calculates an emergency route using OSRM
3. Identifies infrastructure points along that route
4. Orders them according to their distance along the route
5. Tracks the emergency vehicle's progress along the same route
6. Activates "clear the lane" messaging for upcoming checkpoints
7. Restores normal operation after the emergency vehicle passes

This approach helps avoid unreliable on/off behavior caused by normal GPS fluctuations.

### Unified Dashboard

The dashboard provides a centralized interface containing:

- Traffic analytics
- Current traffic information
- Historical information
- Junction information
- Manual control and overrides
- Emergency corridor status
- Live map visualization
- VMS status

---

## How It Works

**Traffic signal pipeline:**

```text
Traffic Camera
      |
      v
YOLO Vehicle Detection
      |
      v
Vehicle Classification
      |
      v
PCU Calculation
      |
      v
Traffic Demand Estimation
      |
      v
Webster Signal Timing Formula
      |
      v
Dynamic Signal Control
```

**Emergency corridor pipeline:**

```text
Emergency Vehicle
      |
      v
Destination Selection
      |
      v
OSRM Routing
      |
      v
GPS Tracking
      |
      v
Distance-Along-Route Calculation
      |
      +------------------+
      |                  |
      v                  v
Traffic Signals       VMS Boards
      |                  |
      v                  v
Green Priority       Clear Lane
      |                  |
      +--------+---------+
               |
               v
      Emergency Corridor
```

---

## Dynamic Signal Timing

I²TMS uses Webster's Signal Timing Formula, an established traffic-engineering method.

**Cycle Length**

```text
C = (1.5 x L + 5) / (1 - Y)
```

- `C` = total cycle length
- `L` = total lost time
- `Y` = sum of approach flow ratios

**Flow Ratio**

```text
y = q / s
```

- `q` = traffic demand
- `s` = saturation flow
- `y` = approach flow ratio

**Green Time Allocation**

```text
g = (y / Y) x (C - L)
```

Traffic demand is obtained from camera-based vehicle detection and converted into PCU values before being used by the signal-timing logic.

### Passenger Car Unit (PCU) Reference

Different vehicle types occupy different amounts of road space. I²TMS uses PCU values when calculating traffic demand.

| Vehicle Type | PCU |
|---|---:|
| Car | 1 |
| Two-wheeler | 0.5 |
| Auto | 0.8 |
| Bus / Truck | 3 |

These values create a more meaningful representation of mixed traffic conditions.

---

## Green Corridor Logic

A major design goal of I²TMS is to clear traffic between junctions as well as at junctions.

The system maintains a digital map of:

- Junctions
- VMS boards
- Emergency routes

Once a route is calculated, each infrastructure point is assigned a position based on its distance along the route.

```text
Start -> VMS 1 -> Junction A -> VMS 2 -> VMS 3 -> Junction B -> Destination
```

As the emergency vehicle moves:

- Upcoming VMS boards display "Clear the Lane"
- Passed VMS boards return to their normal message
- Approaching junctions receive green priority
- Passed junctions return to normal adaptive signal timing

---

## Computer Vision

The system uses YOLO-based vehicle detection on sample junction footage.

The detection pipeline provides:

- Vehicle detection
- Vehicle classification
- Vehicle counts
- Traffic information for each approach
- PCU-based traffic demand

The detected information is then used by the traffic-management logic.

---

## Emergency Vehicle Tracking

The Green Corridor module uses GPS-based tracking to determine the emergency vehicle's current position.

For prototype demonstration, GPS movement can be simulated along the calculated OSRM route. This allows the complete emergency-corridor workflow to be demonstrated without requiring physical GPS hardware.

---

## ANPR Integration

A bonnet-mounted camera on the emergency vehicle can be used for Automatic Number Plate Recognition (ANPR).

When an emergency corridor is actively engaged, vehicles blocking the corridor can be identified and flagged for targeted enforcement. This mechanism operates only while the relevant emergency corridor is active.

---

## Prototype Demonstration Flow

```text
Enter Emergency Destination
        |
        v
Calculate Route
        |
        v
Display Route on Map
        |
        v
Simulate Emergency Vehicle Movement
        |
        v
Track Distance Along Route
        |
        v
Activate Upcoming VMS Boards
        |
        v
Give Approaching Junctions Green Priority
        |
        v
Emergency Vehicle Passes
        |
        v
Restore Normal Traffic Operation
```

Real YOLO-based vehicle detection runs in parallel, providing live traffic information to the system throughout.

---

## System Architecture

| Input Sources | Processing Layer | Control Logic | Dashboard |
|---|---|---|---|
| Camera Feed | YOLO Detection | Signal Timing | Traffic Analytics |
| GPS | PCU Calculation | Green Corridor | Live Map |
| Emergency Destination | OSRM Routing | VMS Coordination | Signal Status |
| Infrastructure Data | Route Tracking | ANPR Events | VMS Status |
| | Webster Calculation | | Manual Controls |

Data flows left to right: input sources feed the processing layer, which drives the control logic, which in turn updates the dashboard.

---

## Technology Stack

| Category | Technologies |
|---|---|
| Frontend | React |
| Computer Vision | YOLO |
| Routing | OSRM, OpenStreetMap |
| Traffic Engineering | Webster's Signal Timing Formula, Passenger Car Unit (PCU) |
| Location and Enforcement | GPS Tracking, ANPR |
| Infrastructure | Variable Message Signs (VMS) |
| Domain | Intelligent Transportation Systems (ITS) |

---

## Problem Statement

Urban traffic systems often rely on fixed signal timings that do not respond effectively to changing traffic conditions. At the same time, emergency vehicles can lose valuable time because traffic remains congested along the route.

I²TMS addresses these challenges by combining real-time traffic detection, adaptive signal timing, route intelligence, and emergency corridor coordination into a unified traffic-management prototype.

---

## Use Cases

- Ambulance emergency corridors
- Fire and rescue vehicle routing
- Adaptive traffic signal management
- Smart-city traffic management
- Traffic monitoring and analytics
- Emergency route coordination

---

## Getting Started

> Fill in the exact commands for your stack below — this section is a template based on the tech stack referenced in this project.

### Prerequisites

- Node.js 18.x or later
- Python 3.9 or later (for the YOLO detection service)
- Git

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/<your-username>/I2TMS.git
cd I2TMS

# 2. Install frontend dependencies
cd dashboard
npm install

# 3. Install backend / computer vision service dependencies
cd ../backend
pip install -r requirements.txt

# 4. Start the backend service
python app.py

# 5. Start the dashboard
cd ../dashboard
npm run dev
```

The dashboard will be available at `http://localhost:5173` (or your configured port).

---

## Future Scope

The current system is a software prototype designed for demonstration and validation. Potential future extensions include:

- Integration with real traffic-signal controllers
- Deployment of physical VMS communication
- Live city-wide traffic sensor integration
- Real GPS hardware integration
- Larger-scale traffic prediction
- Integration with municipal traffic infrastructure
- Production-grade ANPR and enforcement integration

---

## Project Status

**Prototype / Hackathon Project**

The system is designed to demonstrate the complete concept through a unified software application, simulated emergency-vehicle movement, route-based corridor control, and real computer-vision-based vehicle detection.

---

## Contributing

Contributions are welcome. To get started:

1. Fork the repository and clone it locally
2. Create a feature branch (`git checkout -b feat/your-feature`)
3. Make your changes and test locally
4. Commit using Conventional Commits (`feat:`, `fix:`, `docs:`, etc.)
5. Push to your fork and open a pull request

Please open an issue first for major changes so the approach can be discussed.

---

## Team

Developed as a collaborative project with dedicated work across:

- Backend Development
- Frontend Development
- AI/ML and Computer Vision
- System Integration

<!-- Optionally add a table here with names, roles, and GitHub/LinkedIn links -->

---

## Technical Reference

The project architecture, algorithms, workflow, demonstration strategy, and technical decisions are documented in the team's technical reference document.

---

## Acknowledgements

- OpenStreetMap for map data
- OSRM (Open Source Routing Machine) for route calculation
- YOLO for vehicle detection
- Traffic-engineering principles based on Webster's Signal Timing Formula
- [SORT (Simple Online and Realtime Tracking)](https://github.com/abewley/sort) by Alex Bewley — used for multi-object vehicle tracking, licensed under GPL-3.0
- [Automatic Number Plate Recognition (YOLOv8 + EasyOCR)](https://github.com/computervisioneng/automatic-number-plate-recognition-python-yolov8) — used for the ANPR pipeline, licensed under AGPL-3.0

See [NOTICE.md](NOTICE.md) for full third-party attribution details.

---

## License

This project incorporates code derived from [SORT](https://github.com/abewley/sort) (GPL-3.0) and from a [YOLOv8-based ANPR project](https://github.com/computervisioneng/automatic-number-plate-recognition-python-yolov8) (AGPL-3.0). Because both are copyleft licenses, this repository as a whole is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)** — see [LICENSE](LICENSE).

In practice this means:

- The full source code of this project must remain publicly available.
- If a modified version of this project is run as a network-accessible service, users interacting with it over the network must be offered access to the corresponding source code (AGPL-3.0, §13).
- Any fork or redistribution must preserve this license and the attributions in [NOTICE.md](NOTICE.md).

This project can no longer be distributed under MIT or any other permissive license, since it builds on GPL-3.0 and AGPL-3.0 licensed code.

---

### Key Idea

I²TMS transforms traffic management from fixed, reactive control into an intelligent, data-driven system capable of dynamically responding to traffic conditions and creating coordinated emergency corridors.

---

*Last modified for demonstration purposes.*
