-- =============================================================================
-- PDPTW Solver Platform — Database Schema
-- Compatible: drawsql.app / PostgreSQL
-- =============================================================================

-- ─── AUTH ────────────────────────────────────────────────────────────────────

CREATE TABLE users (
    id              SERIAL       PRIMARY KEY,
    email           VARCHAR(255) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255) NOT NULL,
    role            VARCHAR(20)  NOT NULL,          -- admin | algo_tester | dataset_provider | metric_provider
    is_active       BOOLEAN      NOT NULL,
    created_at      TIMESTAMP    NOT NULL
);

CREATE TABLE refresh_tokens (
    id         SERIAL       PRIMARY KEY,
    user_id    INT          NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    token      VARCHAR(512) NOT NULL UNIQUE,
    expires_at TIMESTAMP    NOT NULL,
    revoked    BOOLEAN      NOT NULL,
    created_at TIMESTAMP    NOT NULL
);

-- ─── PERMISSIONS ─────────────────────────────────────────────────────────────

CREATE TABLE permissions (
    id          SERIAL       PRIMARY KEY,
    code        VARCHAR(100) NOT NULL UNIQUE,    -- vd: algorithm:update
    resource    VARCHAR(50)  NOT NULL,           -- vd: algorithm, dataset
    action      VARCHAR(20)  NOT NULL,           -- read | create | update | delete | share | admin
    description TEXT
);

-- Associative entity: role <-> permission (nhiều-nhiều)
CREATE TABLE role_permissions (
    role          VARCHAR(20) NOT NULL,
    permission_id INT         NOT NULL REFERENCES permissions (id),
    PRIMARY KEY (role, permission_id)
);

-- ─── VRP VARIANTS ────────────────────────────────────────────────────────────

CREATE TABLE vrp_variants (
    id          SERIAL       PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,    -- PDPTW | VRPTW | 2E-VRP | ...
    description TEXT,
    paper_link  VARCHAR(512),
    is_active   BOOLEAN      NOT NULL
);

CREATE TABLE variant_constraints (
    id                   SERIAL       PRIMARY KEY,
    variant_id           INT          NOT NULL REFERENCES vrp_variants (id),
    constraint_id        VARCHAR(100) NOT NULL,  -- time_window | capacity | precedence | pairing
    description          TEXT,
    constraint_statement TEXT                    -- LaTeX hoặc mô tả kỹ thuật
);

-- ─── ALGORITHMS ──────────────────────────────────────────────────────────────

CREATE TABLE algorithms (
    id               SERIAL       PRIMARY KEY,
    name             VARCHAR(255) NOT NULL UNIQUE,
    description      TEXT,
    is_system        BOOLEAN      NOT NULL,       -- TRUE = built-in (ALNS), FALSE = custom upload
    plugin_folder    VARCHAR(255),                -- solver/plugins/<name>/
    entry_file       VARCHAR(255),                -- plugin.py
    selected_metrics TEXT,                        -- JSON: ["total_distance", ...]
    flow_steps       TEXT,                        -- JSON: [{phase, description, ...}]
    owner_id         INT          REFERENCES users (id),
    visibility       VARCHAR(20)  NOT NULL,       -- public | private | shared
    created_at       TIMESTAMP    NOT NULL
);

-- Associative entity: algorithm <-> vrp_variant (nhiều-nhiều)
CREATE TABLE algorithm_variants (
    algorithm_id INT NOT NULL REFERENCES algorithms  (id),
    variant_id   INT NOT NULL REFERENCES vrp_variants (id),
    PRIMARY KEY (algorithm_id, variant_id)
);

-- Associative entity: chia sẻ algorithm với user cụ thể
CREATE TABLE algorithm_shares (
    algorithm_id INT       NOT NULL REFERENCES algorithms (id),
    user_id      INT       NOT NULL REFERENCES users      (id),
    shared_at    TIMESTAMP NOT NULL,
    PRIMARY KEY (algorithm_id, user_id)
);

-- ─── METRICS ─────────────────────────────────────────────────────────────────

CREATE TABLE metrics (
    id            SERIAL       PRIMARY KEY,
    name          VARCHAR(255) NOT NULL UNIQUE,
    description   TEXT,
    is_system     BOOLEAN      NOT NULL,
    plugin_folder VARCHAR(255),
    entry_file    VARCHAR(255),
    owner_id      INT          REFERENCES users (id),
    visibility    VARCHAR(20)  NOT NULL,
    created_at    TIMESTAMP    NOT NULL
);

-- Associative entity: chia sẻ metric với user cụ thể
CREATE TABLE metric_shares (
    metric_id INT       NOT NULL REFERENCES metrics (id),
    user_id   INT       NOT NULL REFERENCES users   (id),
    shared_at TIMESTAMP NOT NULL,
    PRIMARY KEY (metric_id, user_id)
);

-- ─── DATASETS & INSTANCES ────────────────────────────────────────────────────

CREATE TABLE datasets (
    id           SERIAL       PRIMARY KEY,
    name         VARCHAR(255) NOT NULL UNIQUE,
    dataset_type VARCHAR(20)  NOT NULL,           -- sartori | lilim | custom
    variant_id   INT          REFERENCES vrp_variants (id),
    folder_path  VARCHAR(500) NOT NULL,
    description  TEXT,
    owner_id     INT          REFERENCES users (id),
    visibility   VARCHAR(20)  NOT NULL,
    created_at   TIMESTAMP    NOT NULL
);

-- Associative entity: chia sẻ dataset với user cụ thể
CREATE TABLE dataset_shares (
    dataset_id INT       NOT NULL REFERENCES datasets (id),
    user_id    INT       NOT NULL REFERENCES users    (id),
    shared_at  TIMESTAMP NOT NULL,
    PRIMARY KEY (dataset_id, user_id)
);

-- Weak entity: file instance trong dataset
CREATE TABLE instances (
    id            SERIAL       PRIMARY KEY,
    dataset_id    INT          NOT NULL REFERENCES datasets (id),
    filename      VARCHAR(255) NOT NULL,
    instance_name VARCHAR(255) NOT NULL,           -- tên không đuôi, dùng để tra BKS
    num_nodes     INT,
    num_requests  INT,
    capacity      FLOAT,
    horizon       INT,
    parsed_at     TIMESTAMP    NOT NULL,
    UNIQUE (dataset_id, filename)
);

CREATE TABLE best_known_solutions (
    id            SERIAL       PRIMARY KEY,
    instance_name VARCHAR(255) NOT NULL UNIQUE,
    dataset_type  VARCHAR(20)  NOT NULL,           -- sartori | lilim | ropke_cordeau | ...
    bks_nv        INT          NOT NULL,
    bks_cost      FLOAT        NOT NULL,
    source        VARCHAR(255),
    year          SMALLINT,
    added_at      TIMESTAMP    NOT NULL
);

-- ─── JOBS ────────────────────────────────────────────────────────────────────

CREATE TABLE jobs (
    id             SERIAL       PRIMARY KEY,
    instance_name  VARCHAR(255) NOT NULL,
    algorithm_id   INT          REFERENCES algorithms (id),
    method         VARCHAR(50)  NOT NULL,           -- greedy | regret | alns
    time_limit_sec FLOAT        NOT NULL,
    seed           INT          NOT NULL,
    status         VARCHAR(20)  NOT NULL,           -- pending | running | done | failed | cancelled
    owner_id       INT          NOT NULL REFERENCES users (id),
    created_at     TIMESTAMP    NOT NULL,
    started_at     TIMESTAMP,
    finished_at    TIMESTAMP,
    error_msg      TEXT
);

-- Associative entity: job được đánh giá bằng metric nào
CREATE TABLE job_metrics (
    job_id    INT NOT NULL REFERENCES jobs    (id),
    metric_id INT NOT NULL REFERENCES metrics (id),
    PRIMARY KEY (job_id, metric_id)
);

-- ─── SOLUTIONS ───────────────────────────────────────────────────────────────

CREATE TABLE solutions (
    id             SERIAL    PRIMARY KEY,
    job_id         INT       NOT NULL UNIQUE REFERENCES jobs (id),
    num_vehicles   INT       NOT NULL,
    total_distance FLOAT     NOT NULL,
    total_cost     FLOAT,
    dataset_type   VARCHAR(50),
    init_nv        INT,
    init_cost      FLOAT,
    iterations     INT,
    elapsed_sec    FLOAT,
    hostname       VARCHAR(255),
    os_info        VARCHAR(512),
    cpu_info       VARCHAR(512),
    ram_gb         FLOAT,
    cpu_usage_pct  FLOAT,
    created_at     TIMESTAMP NOT NULL
);

-- Weak entity: route trong solution
CREATE TABLE routes (
    id            SERIAL PRIMARY KEY,
    solution_id   INT    NOT NULL REFERENCES solutions (id),
    route_index   INT    NOT NULL,
    num_stops     INT,
    travel_time   FLOAT,
    total_waiting FLOAT,
    UNIQUE (solution_id, route_index)
);

-- Weak entity: điểm dừng trong route
CREATE TABLE route_stops (
    id            SERIAL     PRIMARY KEY,
    route_id      INT        NOT NULL REFERENCES routes (id),
    position      INT        NOT NULL,
    node_id       INT        NOT NULL,
    stop_type     VARCHAR(10),                  -- P | D | depot
    arrival_time  FLOAT,
    service_start FLOAT,
    service_end   FLOAT,
    load_after    FLOAT,
    tw_early      FLOAT,
    tw_late       FLOAT,
    UNIQUE (route_id, position)
);

-- Weak entity: kết quả từng metric sau khi job hoàn tất
CREATE TABLE solution_metric_results (
    id          SERIAL    PRIMARY KEY,
    solution_id INT       NOT NULL REFERENCES solutions (id),
    metric_id   INT       NOT NULL REFERENCES metrics   (id),
    value       FLOAT,
    value_text  TEXT,
    computed_at TIMESTAMP NOT NULL,
    UNIQUE (solution_id, metric_id)
);

