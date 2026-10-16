"""Create normalized FlexProof run, telemetry, verification, and report tables."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial_records"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("scenario_configs",
        sa.Column("scenario_hash", sa.String(64), primary_key=True),
        sa.Column("scenario_id", sa.String(80), nullable=False),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_scenario_configs_scenario_id", "scenario_configs", ["scenario_id"])
    op.create_table("simulation_runs",
        sa.Column("run_id", sa.String(120), primary_key=True),
        sa.Column("scenario_hash", sa.String(64), sa.ForeignKey("scenario_configs.scenario_hash"), nullable=False),
        sa.Column("controller", sa.String(64), nullable=False),
        sa.Column("controller_version", sa.String(80), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("execution_status", sa.String(48), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("result_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_simulation_runs_scenario_hash", "simulation_runs", ["scenario_hash"])
    op.create_index("ix_simulation_runs_created_at", "simulation_runs", ["created_at"])
    op.create_table("telemetry_intervals",
        sa.Column("run_id", sa.String(120), sa.ForeignKey("simulation_runs.run_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("phase", sa.String(16), primary_key=True),
        sa.Column("step", sa.Integer(), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False))
    op.create_table("verification_records",
        sa.Column("run_id", sa.String(120), sa.ForeignKey("simulation_runs.run_id", ondelete="CASCADE"), primary_key=True),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("evidence_hash", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_table("report_metadata",
        sa.Column("report_id", sa.String(120), primary_key=True),
        sa.Column("run_id", sa.String(120), sa.ForeignKey("simulation_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("format", sa.String(16), nullable=False),
        sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_report_metadata_run_id", "report_metadata", ["run_id"])


def downgrade():
    op.drop_index("ix_report_metadata_run_id", table_name="report_metadata")
    op.drop_table("report_metadata")
    op.drop_table("verification_records")
    op.drop_table("telemetry_intervals")
    op.drop_index("ix_simulation_runs_created_at", table_name="simulation_runs")
    op.drop_index("ix_simulation_runs_scenario_hash", table_name="simulation_runs")
    op.drop_table("simulation_runs")
    op.drop_index("ix_scenario_configs_scenario_id", table_name="scenario_configs")
    op.drop_table("scenario_configs")
