"""Explicit deferrable-job ledger in MW-equivalent-hours."""
from dataclasses import dataclass, field
from math import isfinite

TOL = 1e-9

@dataclass(slots=True)
class Job:
    job_id: str
    arrival_minute: int
    remaining_work_mwh: float
    max_power_mw: float
    deadline_minute: int
    max_deferral_minutes: int
    started_minute: int | None = None
    completed_minute: int | None = None
    deadline_missed: bool = False
    max_deferral_missed: bool = False

    def __post_init__(self):
        if not self.job_id:
            raise ValueError("job_id must be nonempty")
        if self.arrival_minute < 0 or self.deadline_minute <= self.arrival_minute:
            raise ValueError("job arrival/deadline interval is invalid")
        if self.max_deferral_minutes < 0:
            raise ValueError("max_deferral_minutes must be nonnegative")
        if not isfinite(self.remaining_work_mwh) or self.remaining_work_mwh < 0:
            raise ValueError("remaining_work_mwh must be finite and nonnegative")
        if not isfinite(self.max_power_mw) or self.max_power_mw < 0:
            raise ValueError("max_power_mw must be finite and nonnegative")

    @property
    def latest_start_minute(self) -> int:
        return min(self.deadline_minute, self.arrival_minute + self.max_deferral_minutes)

@dataclass(slots=True)
class WorkloadQueue:
    jobs: list[Job] = field(default_factory=list)
    violations: list[dict] = field(default_factory=list)

    def add(self, job: Job) -> None:
        if any(existing.job_id == job.job_id for existing in self.jobs):
            raise ValueError(f"duplicate job_id: {job.job_id}")
        self.jobs.append(job)

    @property
    def backlog_mwh(self) -> float:
        return sum(max(0.0, job.remaining_work_mwh) for job in self.jobs)

    @property
    def all_complete(self) -> bool:
        return self.backlog_mwh <= TOL

    def dispatch(self, *, available_power_mw: float, start_minute: int,
                 interval_minutes: int) -> dict:
        """Serve available jobs in earliest-deadline order without discarding work."""
        if not isfinite(available_power_mw) or available_power_mw < 0:
            raise ValueError("available_power_mw must be finite and nonnegative")
        if start_minute < 0 or interval_minutes <= 0:
            raise ValueError("dispatch time and interval must be valid")
        dt_hours = interval_minutes / 60.0
        end_minute = start_minute + interval_minutes
        remaining_power = available_power_mw
        used_power = 0.0
        served_work = 0.0
        job_records = []
        ordered = sorted(self.jobs, key=lambda j: (j.deadline_minute, j.arrival_minute, j.job_id))
        for job in ordered:
            if job.remaining_work_mwh <= TOL or job.arrival_minute > start_minute:
                continue
            if start_minute >= job.deadline_minute or end_minute > job.deadline_minute or remaining_power <= TOL:
                continue
            power = min(job.max_power_mw, remaining_power,
                        job.remaining_work_mwh / dt_hours)
            if power <= TOL:
                continue
            if job.started_minute is None:
                job.started_minute = max(start_minute, job.arrival_minute)
            work = min(job.remaining_work_mwh, power * dt_hours)
            job.remaining_work_mwh = max(0.0, job.remaining_work_mwh - work)
            remaining_power -= power
            used_power += power
            served_work += work
            record = {"job_id": job.job_id, "power_mw": power, "work_mwh": work}
            if job.remaining_work_mwh <= TOL:
                job.remaining_work_mwh = 0.0
                job.completed_minute = end_minute
                record["completed_minute"] = end_minute
            job_records.append(record)

        for job in self.jobs:
            if job.remaining_work_mwh <= TOL:
                continue
            if end_minute > job.latest_start_minute and job.started_minute is None and not job.max_deferral_missed:
                job.max_deferral_missed = True
                self.violations.append({"type": "max_deferral_missed", "job_id": job.job_id,
                                        "minute": end_minute, "remaining_work_mwh": job.remaining_work_mwh})
            if end_minute >= job.deadline_minute and not job.deadline_missed:
                job.deadline_missed = True
                self.violations.append({"type": "deadline_missed", "job_id": job.job_id,
                                        "minute": end_minute, "remaining_work_mwh": job.remaining_work_mwh})
        return {"power_mw": used_power, "work_mwh": served_work, "jobs": job_records,
                "backlog_mwh": self.backlog_mwh}

    def snapshot(self) -> list[dict]:
        return [{"job_id": j.job_id, "arrival_minute": j.arrival_minute,
                 "remaining_work_mwh": j.remaining_work_mwh, "max_power_mw": j.max_power_mw,
                 "deadline_minute": j.deadline_minute, "max_deferral_minutes": j.max_deferral_minutes,
                 "started_minute": j.started_minute, "completed_minute": j.completed_minute,
                 "deadline_missed": j.deadline_missed,
                 "max_deferral_missed": j.max_deferral_missed} for j in self.jobs]
