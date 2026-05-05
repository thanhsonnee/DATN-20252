from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr

from typing import List

from app.db.models import JobStatus, OrderStatus, UserRole, VehicleStatus


# ── Auth ───────────────────────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    role: Optional[UserRole] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    full_name: str
    user_id: int


# ── Users ──────────────────────────────────────────────────────────────────────


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: UserRole = UserRole.algo_tester  # type: ignore[assignment]


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None
    password: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Fleet ──────────────────────────────────────────────────────────────────────


class VehicleCreate(BaseModel):
    plate: str
    capacity: float
    status: VehicleStatus = VehicleStatus.available
    notes: Optional[str] = None


class VehicleUpdate(BaseModel):
    plate: Optional[str] = None
    capacity: Optional[float] = None
    status: Optional[VehicleStatus] = None
    notes: Optional[str] = None


class VehicleOut(BaseModel):
    id: int
    plate: str
    capacity: float
    status: VehicleStatus
    notes: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Instances ──────────────────────────────────────────────────────────────────


class InstanceInfo(BaseModel):
    name: str
    path: str = ""
    num_requests: Optional[int] = None
    num_vehicles: Optional[int] = None
    capacity: Optional[float] = None
    is_folder: bool = False
    file_count: Optional[int] = None
    uploaded_by: Optional[str] = None
    uploaded_at: Optional[str] = None
    uploaded_by_id: Optional[int] = None
    visibility: Optional[str] = "public"  # "public" | "private" | "shared"
    shared_with: Optional[list] = None    # list of user IDs


# ── Jobs ───────────────────────────────────────────────────────────────────────


class JobCreate(BaseModel):
    instance_name: str
    method: str = "greedy"        # "greedy" | "regret"
    time_limit_sec: float = 60.0
    seed: int = 0


class SolutionSummary(BaseModel):
    id: int
    num_vehicles: int
    total_distance: float
    total_cost: Optional[float] = None
    dataset_type: Optional[str] = None

    model_config = {"from_attributes": True}


class JobOut(BaseModel):
    id: int
    instance_name: str
    status: JobStatus
    method: str
    time_limit_sec: float
    seed: int
    owner_id: int
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    error_msg: Optional[str]
    solution: Optional[SolutionSummary] = None

    model_config = {"from_attributes": True}


# ── Solutions ──────────────────────────────────────────────────────────────────


class MetricResultItem(BaseModel):
    metric_name: str
    value: Optional[float] = None
    value_text: Optional[str] = None


class RouteStopOut(BaseModel):
    position: int
    node_id: int
    stop_type: Optional[str] = None
    arrival_time: Optional[float] = None
    service_start: Optional[float] = None
    tw_early: Optional[float] = None
    tw_late: Optional[float] = None

    model_config = {"from_attributes": True}


class RouteOut(BaseModel):
    route_index: int
    num_stops: Optional[int] = None
    travel_time: Optional[float] = None
    total_waiting: Optional[float] = None
    stops: list[RouteStopOut]

    model_config = {"from_attributes": True}


class SolutionOut(BaseModel):
    id: int
    job_id: int
    instance_name: str = ""
    method: str = ""
    num_vehicles: int
    total_distance: float
    total_cost: Optional[float] = None
    dataset_type: Optional[str] = None
    created_at: datetime
    routes: list[RouteOut]
    # Performance
    iterations: Optional[int] = None
    elapsed_sec: Optional[float] = None
    init_cost: Optional[float] = None
    init_nv: Optional[int] = None
    # Environment
    hostname: Optional[str] = None
    os_info: Optional[str] = None
    cpu_info: Optional[str] = None
    ram_gb: Optional[float] = None
    cpu_usage_pct: Optional[float] = None
    # Metrics
    metric_results: Optional[list[MetricResultItem]] = None

    model_config = {"from_attributes": True}


class SolutionListItem(BaseModel):
    id: int
    job_id: int
    num_vehicles: int
    total_distance: float
    total_cost: Optional[float] = None
    dataset_type: Optional[str] = None
    elapsed_sec: Optional[float] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SolutionListResponse(BaseModel):
    code: str = "SUCCESS"
    data: list[SolutionListItem]
    total: int


class BksEntry(BaseModel):
    instance_name: str
    bks_nv: int
    bks_cost: float
    reference: str
    date: str


class BaselineOut(BaseModel):
    instance_name: str
    bks_nv: int
    bks_cost: float
    source: Optional[str] = None
    year: Optional[int] = None


class DatasetStats(BaseModel):
    """Aggregated stats for one (dataset, method) group."""
    dataset: str
    method: str
    count: int
    avg_nv: float
    avg_cost: float
    avg_init_cost: Optional[float]
    avg_improve_pct: Optional[float]
    avg_gap_nv_pct: Optional[float]
    avg_gap_cost_pct: Optional[float]
    avg_elapsed_sec: Optional[float]
    avg_iterations: Optional[float]
    avg_iter_per_sec: Optional[float]


class DatasetStatAlgoResult(BaseModel):
    algorithm_name: str
    num_vehicles: Optional[int] = None
    total_cost: Optional[float] = None
    gap_pct: Optional[float] = None


class DatasetStatInstanceRow(BaseModel):
    instance_name: str
    bks_nv: Optional[int] = None
    bks_cost: Optional[float] = None
    results: list[DatasetStatAlgoResult]


class DatasetStatResponse(BaseModel):
    code: str = "SUCCESS"
    data: list[DatasetStatInstanceRow]


# ── VRP Variants ────────────────────────────────────────────────────────────────


class VrpConstraintOut(BaseModel):
    constraint_id: str
    description: Optional[str] = None
    constraint_statement: Optional[str] = None

    model_config = {"from_attributes": True}


class VrpVariantOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    paper_link: Optional[str] = None
    is_active: bool

    model_config = {"from_attributes": True}


class VrpVariantDetailOut(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    paper_link: Optional[str] = None
    is_active: bool
    constraints: list[VrpConstraintOut]

    model_config = {"from_attributes": True}


# ── Orders ─────────────────────────────────────────────────────────────────────


class OrderCreate(BaseModel):
    description: Optional[str] = None
    pickup_address: str
    delivery_address: str
    time_window_start: Optional[str] = None
    time_window_end: Optional[str] = None


class OrderUpdate(BaseModel):
    status: Optional[OrderStatus] = None
    description: Optional[str] = None


class OrderOut(BaseModel):
    id: int
    customer_id: int
    description: Optional[str]
    status: OrderStatus
    pickup_address: str
    delivery_address: str
    time_window_start: Optional[str]
    time_window_end: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Algorithms ─────────────────────────────────────────────────────────────────


class AlgorithmOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    is_system: bool
    filename: Optional[str]
    uploaded_by_id: Optional[int]
    created_at: datetime
    vrp_variant: Optional[str] = None
    selected_metrics: Optional[str] = None  # JSON string
    flow_steps: Optional[str] = None         # JSON string: [{phase, description, loop, components}]
    visibility: str = "public"
    shared_with_ids: Optional[str] = None  # JSON string

    model_config = {"from_attributes": True}


class AlgorithmUpdate(BaseModel):
    vrp_variant: Optional[str] = None
    selected_metrics: Optional[str] = None  # JSON string: ["total_distance", ...]
    description: Optional[str] = None
    flow_steps: Optional[str] = None         # JSON string: [{phase, description, loop, components}]


# ── Metrics ────────────────────────────────────────────────────────────────────


class MetricOut(BaseModel):
    id: int
    name: str
    description: Optional[str]
    is_system: bool
    filename: Optional[str]
    uploaded_by_id: Optional[int]
    visibility: str = "public"
    shared_with_ids: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
