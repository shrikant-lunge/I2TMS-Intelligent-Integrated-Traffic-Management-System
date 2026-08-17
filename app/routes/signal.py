from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from app.ai.adaptive_signal_pipeline import ModelUnavailableError, adaptive_signal_pipeline

signal_bp = Blueprint("signal", __name__)
logger = logging.getLogger(__name__)


def _error(message: str, status_code: int):
    return jsonify({"error": message}), status_code


@signal_bp.route("/api/signal/compute/green-time", methods=["POST"])
def compute_green_time():
    junction_name = (request.form.get("junction_name") or "").strip()
    direction = (request.form.get("direction") or "").strip().lower()
    uploaded_file = request.files.get("file")

    if not junction_name:
        return _error("junction_name is required", 400)
    if not direction:
        return _error("direction is required", 400)
    if not uploaded_file or not uploaded_file.filename:
        return _error("missing file", 400)

    try:
        file_bytes = uploaded_file.read()
        if not file_bytes:
            return _error("missing file", 400)

        result = adaptive_signal_pipeline.process(
            uploaded_file.filename,
            file_bytes,
            junction_name,
            direction,
        )
        return jsonify(result)
    except LookupError as exc:
        return _error(str(exc), 404)
    except ValueError as exc:
        message = str(exc).strip()
        if message == "invalid direction":
            return _error("invalid direction", 400)
        if message == "unsupported file type":
            return _error("unsupported file type", 400)
        return _error(message or "pipeline processing error", 400)
    except ModelUnavailableError as exc:
        logger.exception("YOLO model unavailable")
        return _error(str(exc) or "YOLO model unavailable", 500)
    except Exception:
        logger.exception("pipeline processing error")
        return _error("pipeline processing error", 500)