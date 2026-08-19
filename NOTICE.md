# Third-Party Notices

This project, I²TMS (Intelligent Integrated Traffic Management System), incorporates code
derived from the following third-party open-source projects. Because those projects are
licensed under the GNU GPLv3 and GNU AGPLv3, **this repository as a whole is licensed under
the GNU Affero General Public License v3.0 (AGPL-3.0)** — see [LICENSE](LICENSE).

## 1. SORT (Simple Online and Realtime Tracking)

- **Source:** https://github.com/abewley/sort
- **Author:** Alex Bewley (alex@bewley.ai)
- **License:** GNU General Public License v3.0 (GPL-3.0)
- **Used for:** Multi-object tracking logic in this project's vehicle-tracking pipeline.
- **License text:** [THIRD_PARTY_LICENSES/GPL-3.0 (sort).txt](<THIRD_PARTY_LICENSES/GPL-3.0 (sort).txt>)

## 2. Automatic Number Plate Recognition (YOLOv8 + EasyOCR)

- **Source:** https://github.com/computervisioneng/automatic-number-plate-recognition-python-yolov8
- **License:** GNU Affero General Public License v3.0 (AGPL-3.0)
- **Used for:** The ANPR (license-plate detection and OCR) pipeline in this project.
- **License text:** [THIRD_PARTY_LICENSES/AGPL-3.0 (anpr).txt](<THIRD_PARTY_LICENSES/AGPL-3.0 (anpr).txt>)

## What this means for this repository

- The complete source code of this project must remain publicly available under AGPL-3.0.
- If this application (or a modified version of it) is run as a network service that users
  interact with remotely, the AGPL-3.0 requires that those users be offered access to the
  corresponding source code (AGPL-3.0, §13).
- Any redistribution or derivative work must preserve this licensing and these attributions.
- The MIT license previously referenced for this repository does not apply and has been
  replaced by AGPL-3.0 to comply with the licenses of the above components.

This notice is provided for attribution and compliance purposes and is not legal advice.
If you need certainty about your specific use case, consult a qualified attorney.
