"""
Database models and setup using SQLAlchemy with SQLite.
"""

import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime, Text, Enum
)
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency for FastAPI endpoints."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =============================================================================
# Emergency Events
# =============================================================================
class EmergencyEventDB(Base):
    __tablename__ = "emergency_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(50), unique=True, nullable=False, index=True)
    ambulance_id = Column(String(50), default="AMB-DEFAULT-01")
    destination = Column(String(255), nullable=False)
    start_lat = Column(Float, nullable=True)
    start_lon = Column(Float, nullable=True)
    dest_lat = Column(Float, nullable=True)
    dest_lon = Column(Float, nullable=True)
    status = Column(String(20), default="ACTIVE")  # ACTIVE, COMPLETED, CANCELLED
    routing_mode = Column(String(20), default="DEMO")  # DEMO, OSRM
    start_time = Column(DateTime, default=datetime.datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


# =============================================================================
# Violations
# =============================================================================
class ViolationDB(Base):
    __tablename__ = "violations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    violation_id = Column(String(50), unique=True, nullable=False, index=True)
    emergency_event_id = Column(String(50), nullable=False, index=True)
    vehicle_tracking_id = Column(Integer, nullable=False)
    vehicle_type = Column(String(30), nullable=True)
    plate_number = Column(String(30), nullable=True)
    plate_confidence = Column(Float, nullable=True)
    detection_confidence = Column(Float, nullable=True)
    violation_type = Column(String(50), default="EMERGENCY_CORRIDOR_BLOCKING")
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    evidence_path = Column(String(500), nullable=True)
    blocking_duration = Column(Float, nullable=True)  # seconds
    movement_status = Column(String(20), nullable=True)  # STOPPED, SLOW
    status = Column(String(30), default="DETECTED")
    # DETECTED, VERIFIED, NEEDS_REVIEW, CHALLAN_GENERATED, REJECTED
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


# =============================================================================
# Plate Records
# =============================================================================
class PlateRecordDB(Base):
    __tablename__ = "plate_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plate_number = Column(String(30), nullable=False, index=True)
    plate_confidence = Column(Float, nullable=True)
    source_mode = Column(String(30), default="LIVE_CAMERA")
    source_value = Column(String(255), nullable=True)
    vehicle_type = Column(String(30), nullable=True)
    status = Column(String(20), default="RECOGNIZED")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    notes = Column(Text, nullable=True)


# =============================================================================
# Challans
# =============================================================================
class ChallanDB(Base):
    __tablename__ = "challans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    challan_id = Column(String(50), unique=True, nullable=False, index=True)
    violation_id = Column(String(50), nullable=False, index=True)
    emergency_event_id = Column(String(50), nullable=False)
    vehicle_number = Column(String(30), nullable=True)
    vehicle_type = Column(String(30), nullable=True)
    violation_type = Column(String(50), default="EMERGENCY_CORRIDOR_BLOCKING")
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    location_lat = Column(Float, nullable=True)
    location_lon = Column(Float, nullable=True)
    evidence_path = Column(String(500), nullable=True)
    confidence_score = Column(Float, nullable=True)
    status = Column(String(30), default="SIMULATED")
    # SIMULATED, GENERATED, PENDING_REVIEW
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


def init_db():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)


def save_plate_record(
    plate_number: str,
    plate_confidence: float = None,
    source_mode: str = "LIVE_CAMERA",
    source_value: str = None,
    vehicle_type: str = None,
    status: str = "RECOGNIZED",
    notes: str = None,
):
    """Persist detected plate numbers for later lookup and operations."""
    if not plate_number:
        return None

    db = SessionLocal()
    try:
        record = PlateRecordDB(
            plate_number=plate_number,
            plate_confidence=plate_confidence,
            source_mode=source_mode,
            source_value=source_value,
            vehicle_type=vehicle_type,
            status=status,
            notes=notes,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record
    except Exception:
        db.rollback()
        return None
    finally:
        db.close()


def get_plate_records(limit: int = 100):
    """Return recent recognized plate numbers."""
    db = SessionLocal()
    try:
        return db.query(PlateRecordDB).order_by(PlateRecordDB.created_at.desc()).limit(limit).all()
    finally:
        db.close()
