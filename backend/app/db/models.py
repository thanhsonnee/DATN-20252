from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UserRole(str, enum.Enum):
    admin = "admin"
    algo_tester = "algo_tester"
    dataset_provider = "dataset_provider"
    metric_provider = "metric_provider"


class JobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


class VehicleStatus(str, enum.Enum):
    available = "available"
    in_use = "in_use"
    maintenance = "maintenance"


class OrderStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    in_transit = "in_transit"
    delivered = "delivered"
    cancelled = "cancelled"


# ── Users ─────────────────────────────────────────────────────────────────────


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, default=UserRole.algo_tester)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    jobs: Mapped[list[Job]] = relationship("Job", back_populates="owner")
    orders: Mapped[list[Order]] = relationship("Order", back_populates="customer")


# ── Fleet ──────────────────────────────────────────────────────────────────────


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    plate: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    capacity: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[VehicleStatus] = mapped_column(Enum(VehicleStatus), default=VehicleStatus.available)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── Solver jobs ────────────────────────────────────────────────────────────────


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    instance_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.pending)
    method: Mapped[str] = mapped_column(String(50), default="alns")  # alns | greedy
    time_limit_sec: Mapped[float] = mapped_column(Float, default=60.0)
    seed: Mapped[int] = mapped_column(Integer, default=0)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    algorithm_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("algorithms.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)

    owner: Mapped[User] = relationship("User", back_populates="jobs")
    solution: Mapped[Solution | None] = relationship("Solution", back_populates="job", uselist=False)


# ── Solutions ──────────────────────────────────────────────────────────────────


class Solution(Base):
    __tablename__ = "solutions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_id: Mapped[int] = mapped_column(Integer, ForeignKey("jobs.id"), unique=True, nullable=False)
    num_vehicles: Mapped[int] = mapped_column(Integer, nullable=False)
    total_distance: Mapped[float] = mapped_column(Float, nullable=False)
    total_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    dataset_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Performance metrics
    iterations: Mapped[int | None] = mapped_column(Integer, nullable=True)
    elapsed_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    init_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    init_nv: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Environment info
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    os_info: Mapped[str | None] = mapped_column(String(512), nullable=True)
    cpu_info: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ram_gb: Mapped[float | None] = mapped_column(Float, nullable=True)
    cpu_usage_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    job: Mapped[Job] = relationship("Job", back_populates="solution")
    routes: Mapped[list[Route]] = relationship("Route", back_populates="solution", order_by="Route.route_index")


# ── Algorithms ────────────────────────────────────────────────────────────────


class Algorithm(Base):
    __tablename__ = "algorithms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)  # file in solver/plugins/
    uploaded_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # VRP variant & metrics selection
    vrp_variant: Mapped[str | None] = mapped_column(String(50), nullable=True)   # e.g. "PDPTW", "2E-VRP"
    selected_metrics: Mapped[str | None] = mapped_column(Text, nullable=True)    # JSON: ["total_distance", ...]
    flow_steps: Mapped[str | None] = mapped_column(Text, nullable=True)          # JSON: [{phase, description, loop, components}]
    # visibility: "public" | "private" | "shared"
    visibility: Mapped[str] = mapped_column(String(20), default="public")
    shared_with_ids: Mapped[str | None] = mapped_column(Text, nullable=True)     # JSON: [1, 2, 3]


# ── Metrics ───────────────────────────────────────────────────────────────────


class Metric(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)  # file in solver/metric_plugins/
    uploaded_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    # visibility: "public" | "private" | "shared"
    visibility: Mapped[str] = mapped_column(String(20), default="public")
    shared_with_ids: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: [1, 2, 3]
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    solution_id: Mapped[int] = mapped_column(Integer, ForeignKey("solutions.id"), nullable=False)
    route_index: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-based

    solution: Mapped[Solution] = relationship("Solution", back_populates="routes")
    stops: Mapped[list[RouteStop]] = relationship("RouteStop", back_populates="route", order_by="RouteStop.position")


class RouteStop(Base):
    __tablename__ = "route_stops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    route_id: Mapped[int] = mapped_column(Integer, ForeignKey("routes.id"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-based
    node_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # Time-window enrichment (populated by solver if available)
    stop_type: Mapped[str | None] = mapped_column(String(10), nullable=True)   # P | D | depot
    arrival_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    service_start: Mapped[float | None] = mapped_column(Float, nullable=True)
    tw_early: Mapped[float | None] = mapped_column(Float, nullable=True)
    tw_late: Mapped[float | None] = mapped_column(Float, nullable=True)

    route: Mapped[Route] = relationship("Route", back_populates="stops")


# ── Orders (v1: benchmark-linked, v2: real customer orders) ───────────────────


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.pending)
    pickup_address: Mapped[str] = mapped_column(String(500), nullable=False)
    delivery_address: Mapped[str] = mapped_column(String(500), nullable=False)
    time_window_start: Mapped[str | None] = mapped_column(String(10), nullable=True)  # HH:MM
    time_window_end: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    customer: Mapped[User] = relationship("User", back_populates="orders")


# ── Auth tokens ────────────────────────────────────────────────────────────────


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship("User")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token: Mapped[str] = mapped_column(String(512), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship("User")


# ── VRP Variants ───────────────────────────────────────────────────────────────


class VrpVariant(Base):
    __tablename__ = "vrp_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    paper_link: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    constraints: Mapped[list[VrpConstraint]] = relationship("VrpConstraint", back_populates="variant", order_by="VrpConstraint.id")


class VrpConstraint(Base):
    __tablename__ = "vrp_constraints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    variant_id: Mapped[int] = mapped_column(Integer, ForeignKey("vrp_variants.id"), nullable=False)
    constraint_id: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "time_window"
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    constraint_statement: Mapped[str | None] = mapped_column(Text, nullable=True)  # LaTeX or technical desc

    variant: Mapped[VrpVariant] = relationship("VrpVariant", back_populates="constraints")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship("User")
