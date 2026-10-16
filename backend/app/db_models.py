"""Normalized records for scenarios, runs, interval telemetry and verification."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ScenarioConfig(Base):
    __tablename__ = "scenario_configs"
    scenario_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    scenario_id: Mapped[str] = mapped_column(String(80), index=True)
    schema_version: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SimulationRun(Base):
    __tablename__ = "simulation_runs"
    run_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    scenario_hash: Mapped[str] = mapped_column(ForeignKey("scenario_configs.scenario_hash"), index=True)
    controller: Mapped[str] = mapped_column(String(64))
    controller_version: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(32))
    execution_status: Mapped[str] = mapped_column(String(48))
    request_payload: Mapped[dict] = mapped_column(JSON)
    result_metadata: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class TelemetryInterval(Base):
    __tablename__ = "telemetry_intervals"
    run_id: Mapped[str] = mapped_column(ForeignKey("simulation_runs.run_id", ondelete="CASCADE"), primary_key=True)
    phase: Mapped[str] = mapped_column(String(16), primary_key=True)
    step: Mapped[int] = mapped_column(Integer, primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON)


class VerificationRecord(Base):
    __tablename__ = "verification_records"
    run_id: Mapped[str] = mapped_column(ForeignKey("simulation_runs.run_id", ondelete="CASCADE"), primary_key=True)
    input_hash: Mapped[str] = mapped_column(String(64))
    evidence_hash: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReportMetadata(Base):
    __tablename__ = "report_metadata"
    report_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("simulation_runs.run_id", ondelete="CASCADE"), index=True)
    format: Mapped[str] = mapped_column(String(16))
    filename: Mapped[str] = mapped_column(String(200))
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
