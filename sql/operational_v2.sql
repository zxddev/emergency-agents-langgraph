-- Enable PostGIS (run once per database)
CREATE EXTENSION IF NOT EXISTS postgis;

-- Schemas
CREATE SCHEMA IF NOT EXISTS iam;
CREATE SCHEMA IF NOT EXISTS operational_v2;

SET search_path TO operational_v2, iam, public;

-- ======================
-- IAM (users/roles/perms)
-- ======================
CREATE TABLE iam.iam_user_v2 (
  id BIGSERIAL PRIMARY KEY,
  username TEXT UNIQUE NOT NULL,
  display_name TEXT,
  email TEXT,
  phone TEXT,
  status TEXT NOT NULL CHECK (status IN ('active','disabled')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE iam.iam_permission_v2 (
  id BIGSERIAL PRIMARY KEY,
  resource_type TEXT NOT NULL CHECK (resource_type IN ('page','api','component')),
  resource_key TEXT NOT NULL,
  action TEXT NOT NULL CHECK (action IN ('view','edit','execute','approve')),
  description TEXT,
  UNIQUE (resource_type, resource_key, action)
);

CREATE TABLE iam.iam_role_v2 (
  id BIGSERIAL PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  description TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE iam.iam_role_permission_v2 (
  role_id BIGINT NOT NULL REFERENCES iam.iam_role_v2(id) ON DELETE CASCADE,
  permission_id BIGINT NOT NULL REFERENCES iam.iam_permission_v2(id) ON DELETE CASCADE,
  PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE iam.iam_user_role_v2 (
  user_id BIGINT NOT NULL REFERENCES iam.iam_user_v2(id) ON DELETE CASCADE,
  role_id BIGINT NOT NULL REFERENCES iam.iam_role_v2(id) ON DELETE CASCADE,
  PRIMARY KEY (user_id, role_id)
);

-- ======================
-- 事件/子灾害/任务
-- ======================
CREATE TABLE incident_v2 (
  id BIGSERIAL PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('active','closed','archived')),
  source TEXT NOT NULL,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE hazard_event_v2 (
  id BIGSERIAL PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  incident_id BIGINT NOT NULL REFERENCES incident_v2(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  hazard_type TEXT,
  status TEXT NOT NULL CHECK (status IN ('active','monitoring','resolved','archived')),
  time_window TSRANGE,
  geometry geometry(Geometry,4326),
  source TEXT NOT NULL,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE mission_v2 (
  id BIGSERIAL PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  incident_id BIGINT NOT NULL REFERENCES incident_v2(id) ON DELETE CASCADE,
  hazard_event_id BIGINT REFERENCES hazard_event_v2(id) ON DELETE SET NULL,
  name TEXT NOT NULL,
  phase TEXT NOT NULL CHECK (phase IN ('preparation','transit','recon','rescue','evaluation')),
  status TEXT NOT NULL CHECK (status IN ('planning','in_progress','completed','failed','cancelled')),
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE task_v2 (
  id BIGSERIAL PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  mission_id BIGINT NOT NULL REFERENCES mission_v2(id) ON DELETE CASCADE,
  hazard_event_id BIGINT REFERENCES hazard_event_v2(id) ON DELETE SET NULL,
  type TEXT NOT NULL,
  priority INT NOT NULL DEFAULT 3,
  time_window TSRANGE,
  location geometry(Point,4326),
  area geometry(Geometry,4326),
  status TEXT NOT NULL CHECK (status IN ('pending','in_progress','completed','failed','cancelled')),
  demand JSONB NOT NULL DEFAULT '{}'::jsonb,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON COLUMN task_v2.status IS 'pending=待执行,in_progress=执行中,completed=完成,failed=失败,cancelled=取消';

-- ======================
-- 图层/实体/障碍/POI/安全点
-- ======================
CREATE TABLE geo_layer_v2 (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT NOT NULL CHECK (category IN ('system','manual','hybrid')),
  access_scope TEXT NOT NULL CHECK (access_scope IN ('view','manage')),
  metadata JSONB DEFAULT '{}'
);

CREATE TABLE geo_entity_v2 (
  id BIGSERIAL PRIMARY KEY,
  layer_id BIGINT REFERENCES geo_layer_v2(id) ON DELETE SET NULL,
  incident_id BIGINT REFERENCES incident_v2(id) ON DELETE CASCADE,
  type TEXT NOT NULL,
  geometry geometry(Geometry,4326) NOT NULL,
  properties JSONB DEFAULT '{}',
  source TEXT NOT NULL CHECK (source IN ('system','manual')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE obstacle_v2 (
  id BIGSERIAL PRIMARY KEY,
  incident_id BIGINT NOT NULL REFERENCES incident_v2(id) ON DELETE CASCADE,
  hazard_event_id BIGINT REFERENCES hazard_event_v2(id) ON DELETE SET NULL,
  type TEXT NOT NULL,
  hardness TEXT NOT NULL CHECK (hardness IN ('hard','soft')),
  time_window TSRANGE,
  geometry geometry(Geometry,4326) NOT NULL,
  severity TEXT CHECK (severity IN ('low','medium','high','critical')),
  source TEXT NOT NULL,
  confidence NUMERIC CHECK (confidence BETWEEN 0 AND 1),
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE obstacle_raster_v2 (
  id BIGSERIAL PRIMARY KEY,
  obstacle_id BIGINT NOT NULL REFERENCES obstacle_v2(id) ON DELETE CASCADE,
  uri TEXT NOT NULL,
  band_info JSONB DEFAULT '{}'
);

CREATE TABLE priority_poi_v2 (
  id BIGSERIAL PRIMARY KEY,
  incident_id BIGINT NOT NULL REFERENCES incident_v2(id) ON DELETE CASCADE,
  hazard_event_id BIGINT REFERENCES hazard_event_v2(id) ON DELETE SET NULL,
  type TEXT NOT NULL,
  priority INT NOT NULL DEFAULT 3,
  geometry geometry(Geometry,4326) NOT NULL,
  time_window TSRANGE,
  source TEXT NOT NULL,
  confidence NUMERIC CHECK (confidence BETWEEN 0 AND 1),
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE task_poi_link_v2 (
  task_id BIGINT NOT NULL REFERENCES task_v2(id) ON DELETE CASCADE,
  poi_id BIGINT NOT NULL REFERENCES priority_poi_v2(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','in_progress','completed','skipped')),
  metadata JSONB DEFAULT '{}',
  PRIMARY KEY (task_id, poi_id)
);

CREATE TABLE safe_site_v2 (
  id BIGSERIAL PRIMARY KEY,
  incident_id BIGINT NOT NULL REFERENCES incident_v2(id) ON DELETE CASCADE,
  hazard_event_id BIGINT REFERENCES hazard_event_v2(id) ON DELETE SET NULL,
  name TEXT NOT NULL,
  category TEXT NOT NULL CHECK (category IN ('shelter','assembly','temporary_safe')),
  geometry geometry(Geometry,4326) NOT NULL,
  capacity INT,
  suitability NUMERIC,
  status TEXT NOT NULL DEFAULT 'available' CHECK (status IN ('available','limited','full','closed')),
  source TEXT NOT NULL,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE safe_site_selection_v2 (
  id BIGSERIAL PRIMARY KEY,
  mission_id BIGINT NOT NULL REFERENCES mission_v2(id) ON DELETE CASCADE,
  task_id BIGINT REFERENCES task_v2(id) ON DELETE SET NULL,
  platform_id BIGINT REFERENCES platform_v2(id) ON DELETE SET NULL,
  rescue_team_id BIGINT REFERENCES rescue_team_v2(id) ON DELETE SET NULL,
  safe_site_id BIGINT NOT NULL REFERENCES safe_site_v2(id) ON DELETE CASCADE,
  selection_reason TEXT,
  status TEXT NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed','accepted','rejected')),
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ======================
-- 能力/平台/队伍
-- ======================
CREATE TABLE capability_profile_v2 (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('ground','uav','usv','robot_dog','personnel')),
  version TEXT NOT NULL DEFAULT 'v1',
  specs JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE platform_v2 (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  platform_type TEXT NOT NULL CHECK (platform_type IN ('vehicle','uav','usv','robot_dog','team')),
  status TEXT NOT NULL CHECK (status IN ('available','busy','offline','maintenance')),
  capability_profile_id BIGINT REFERENCES capability_profile_v2(id),
  home_location geometry(Point,4326),
  org_unit TEXT,
  plate_no TEXT,
  serial_no TEXT,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE platform_capability_v2 (
  platform_id BIGINT PRIMARY KEY REFERENCES platform_v2(id) ON DELETE CASCADE,
  overrides JSONB DEFAULT '{}',
  effective_profile JSONB,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE equipment_loadout_v2 (
  id BIGSERIAL PRIMARY KEY,
  platform_id BIGINT NOT NULL REFERENCES platform_v2(id) ON DELETE CASCADE,
  item_id TEXT NOT NULL,
  qty NUMERIC,
  metadata JSONB DEFAULT '{}',
  UNIQUE (platform_id, item_id)
);

CREATE TABLE rescue_team_v2 (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  org TEXT,
  home_base geometry(Point,4326),
  contact TEXT,
  status TEXT NOT NULL CHECK (status IN ('available','busy','offline')),
  capability_profile_id BIGINT REFERENCES capability_profile_v2(id),
  location geometry(Point,4326),
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE team_member_v2 (
  id BIGSERIAL PRIMARY KEY,
  team_id BIGINT NOT NULL REFERENCES rescue_team_v2(id) ON DELETE CASCADE,
  platform_id BIGINT REFERENCES platform_v2(id) ON DELETE SET NULL,
  person_name TEXT,
  role TEXT,
  contact TEXT,
  metadata JSONB DEFAULT '{}'
);
CREATE UNIQUE INDEX ux_team_member_platform ON team_member_v2(team_id, platform_id) WHERE platform_id IS NOT NULL;
CREATE UNIQUE INDEX ux_team_member_person ON team_member_v2(team_id, person_name, role) WHERE person_name IS NOT NULL;

CREATE TABLE team_platform_v2 (
  id BIGSERIAL PRIMARY KEY,
  team_id BIGINT NOT NULL REFERENCES rescue_team_v2(id) ON DELETE CASCADE,
  platform_id BIGINT REFERENCES platform_v2(id),
  name TEXT,
  capability_profile_id BIGINT REFERENCES capability_profile_v2(id),
  skills TEXT[],
  contact TEXT,
  metadata JSONB DEFAULT '{}'
);
CREATE UNIQUE INDEX ux_team_platform_platform ON team_platform_v2(team_id, platform_id) WHERE platform_id IS NOT NULL;
CREATE UNIQUE INDEX ux_team_platform_name ON team_platform_v2(team_id, name) WHERE name IS NOT NULL;

CREATE TABLE team_location_log_v2 (
  id BIGSERIAL PRIMARY KEY,
  team_id BIGINT NOT NULL REFERENCES rescue_team_v2(id) ON DELETE CASCADE,
  ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  location geometry(Point,4326),
  metadata JSONB DEFAULT '{}'
);

-- ======================
-- 任务指派（内/外）+ 审批
-- ======================
CREATE TABLE task_assignment_v2 (
  id BIGSERIAL PRIMARY KEY,
  task_id BIGINT NOT NULL REFERENCES task_v2(id) ON DELETE CASCADE,
  platform_id BIGINT REFERENCES platform_v2(id),
  rescue_team_id BIGINT REFERENCES rescue_team_v2(id),
  status TEXT NOT NULL CHECK (status IN ('assigned','accepted','rejected','completed','failed')),
  eta_hours NUMERIC,
  route_plan_id BIGINT REFERENCES route_plan_v2(id),
  cost NUMERIC,
  executor_type TEXT NOT NULL CHECK (executor_type IN ('internal_platform','external_team')),
  responsible_user_id BIGINT REFERENCES iam.iam_user_v2(id),
  approval_status TEXT NOT NULL DEFAULT 'pending' CHECK (approval_status IN ('pending','approved','rejected')),
  approved_by BIGINT REFERENCES iam.iam_user_v2(id),
  approved_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (
    (executor_type='internal_platform' AND platform_id IS NOT NULL AND rescue_team_id IS NULL)
    OR
    (executor_type='external_team' AND rescue_team_id IS NOT NULL AND platform_id IS NULL)
  )
);
CREATE UNIQUE INDEX ux_task_assign_internal ON task_assignment_v2(task_id, platform_id) WHERE platform_id IS NOT NULL;
CREATE UNIQUE INDEX ux_task_assign_external ON task_assignment_v2(task_id, rescue_team_id) WHERE rescue_team_id IS NOT NULL;

-- ======================
-- 路径与调度
-- ======================
CREATE TABLE route_plan_v2 (
  id BIGSERIAL PRIMARY KEY,
  code TEXT UNIQUE,
  mission_id BIGINT NOT NULL REFERENCES mission_v2(id) ON DELETE CASCADE,
  platform_id BIGINT REFERENCES platform_v2(id),
  rescue_team_id BIGINT REFERENCES rescue_team_v2(id),
  task_id BIGINT REFERENCES task_v2(id),
  status TEXT NOT NULL CHECK (status IN ('draft','active','completed','failed','cancelled')),
  cost NUMERIC,
  risk JSONB DEFAULT '{}',
  safe_site_id BIGINT REFERENCES safe_site_v2(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (
    (platform_id IS NOT NULL AND rescue_team_id IS NULL)
    OR
    (platform_id IS NULL AND rescue_team_id IS NOT NULL)
  )
);
-- 可按需开启部分唯一索引，限制“同一任务+执行主体”仅一条主路线
-- CREATE UNIQUE INDEX ux_route_plan_internal ON route_plan_v2(task_id, platform_id) WHERE platform_id IS NOT NULL;
-- CREATE UNIQUE INDEX ux_route_plan_external ON route_plan_v2(task_id, rescue_team_id) WHERE rescue_team_id IS NOT NULL;

CREATE TABLE route_candidate_v2 (
  id BIGSERIAL PRIMARY KEY,
  route_plan_id BIGINT NOT NULL REFERENCES route_plan_v2(id) ON DELETE CASCADE,
  rank INT NOT NULL,
  status TEXT NOT NULL DEFAULT 'proposed' CHECK (status IN ('proposed','selected','rejected')),
  cost NUMERIC,
  risk JSONB DEFAULT '{}',
  geometry geometry(LineString,4326),
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (route_plan_id, rank)
);

CREATE TABLE route_segment_v2 (
  id BIGSERIAL PRIMARY KEY,
  route_plan_id BIGINT NOT NULL REFERENCES route_plan_v2(id) ON DELETE CASCADE,
  seq INT NOT NULL,
  start_point geometry(Point,4326),
  end_point geometry(Point,4326),
  geometry geometry(LineString,4326),
  channel TEXT NOT NULL DEFAULT 'ground' CHECK (channel IN ('ground','air','water','foot')),
  distance_km NUMERIC,
  eta_hours NUMERIC,
  metrics JSONB DEFAULT '{}'
);

CREATE TABLE route_point_v2 (
  id BIGSERIAL PRIMARY KEY,
  segment_id BIGINT NOT NULL REFERENCES route_segment_v2(id) ON DELETE CASCADE,
  seq INT NOT NULL,
  pt geometry(Point,4326)
);

CREATE TABLE cost_matrix_cache_v2 (
  id BIGSERIAL PRIMARY KEY,
  mission_id BIGINT NOT NULL REFERENCES mission_v2(id) ON DELETE CASCADE,
  computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  matrix JSONB NOT NULL,
  metadata JSONB DEFAULT '{}'
);

CREATE TABLE cost_matrix_edge_v2 (
  id BIGSERIAL PRIMARY KEY,
  cache_id BIGINT NOT NULL REFERENCES cost_matrix_cache_v2(id) ON DELETE CASCADE,
  platform_id BIGINT NOT NULL REFERENCES platform_v2(id),
  task_id BIGINT NOT NULL REFERENCES task_v2(id),
  cost NUMERIC,
  feasible BOOLEAN NOT NULL DEFAULT true,
  reason TEXT,
  metadata JSONB DEFAULT '{}',
  UNIQUE (cache_id, platform_id, task_id)
);

-- ======================
-- 安全点上方已定义
-- ======================

-- ======================
-- 观测/告警/日志/遥测/轨迹
-- ======================
CREATE TABLE observation_v2 (
  id BIGSERIAL PRIMARY KEY,
  incident_id BIGINT NOT NULL REFERENCES incident_v2(id) ON DELETE CASCADE,
  hazard_event_id BIGINT REFERENCES hazard_event_v2(id) ON DELETE SET NULL,
  source TEXT NOT NULL,
  obs_type TEXT NOT NULL,
  geometry geometry(Geometry,4326) NOT NULL,
  confidence NUMERIC CHECK (confidence BETWEEN 0 AND 1),
  time_window TSRANGE,
  reporter_user_id BIGINT REFERENCES iam.iam_user_v2(id),
  reporter_platform_id BIGINT REFERENCES platform_v2(id) ON DELETE SET NULL,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE obstacle_observation_v2 (
  obstacle_id BIGINT NOT NULL REFERENCES obstacle_v2(id) ON DELETE CASCADE,
  observation_id BIGINT NOT NULL REFERENCES observation_v2(id) ON DELETE CASCADE,
  PRIMARY KEY (obstacle_id, observation_id)
);

CREATE TABLE poi_observation_v2 (
  poi_id BIGINT NOT NULL REFERENCES priority_poi_v2(id) ON DELETE CASCADE,
  observation_id BIGINT NOT NULL REFERENCES observation_v2(id) ON DELETE CASCADE,
  PRIMARY KEY (poi_id, observation_id)
);

CREATE TABLE platform_status_log_v2 (
  id BIGSERIAL PRIMARY KEY,
  platform_id BIGINT NOT NULL REFERENCES platform_v2(id) ON DELETE CASCADE,
  status TEXT NOT NULL CHECK (status IN ('available','busy','offline','maintenance')),
  battery_pct NUMERIC,
  fuel_level NUMERIC,
  health TEXT,
  comm_link TEXT,
  location geometry(Point,4326),
  metrics JSONB DEFAULT '{}',
  ts TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE platform_telemetry_v2 (
  id BIGSERIAL PRIMARY KEY,
  platform_id BIGINT NOT NULL REFERENCES platform_v2(id) ON DELETE CASCADE,
  ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  location geometry(Point,4326),
  speed NUMERIC,
  heading NUMERIC,
  metrics JSONB DEFAULT '{}'
);

CREATE TABLE team_location_log_v2 (
  id BIGSERIAL PRIMARY KEY,
  team_id BIGINT NOT NULL REFERENCES rescue_team_v2(id) ON DELETE CASCADE,
  ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  location geometry(Point,4326),
  metadata JSONB DEFAULT '{}'
);

CREATE TABLE alert_rule_v2 (
  id BIGSERIAL PRIMARY KEY,
  incident_id BIGINT NOT NULL REFERENCES incident_v2(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  trigger JSONB NOT NULL,
  target JSONB NOT NULL,
  action TEXT NOT NULL CHECK (action IN ('notify','push')),
  enabled BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE alert_event_v2 (
  id BIGSERIAL PRIMARY KEY,
  incident_id BIGINT NOT NULL REFERENCES incident_v2(id) ON DELETE CASCADE,
  hazard_event_id BIGINT REFERENCES hazard_event_v2(id) ON DELETE SET NULL,
  rule_id BIGINT REFERENCES alert_rule_v2(id) ON DELETE SET NULL,
  triggered_by JSONB NOT NULL,
  targets JSONB NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('pending','sent','failed')),
  sent_at TIMESTAMPTZ,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ======================
-- 知识资产 / 关联 / 快照 / 审计
-- ======================
CREATE TABLE knowledge_asset_v2 (
  id BIGSERIAL PRIMARY KEY,
  title TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('image','document','case','spec')),
  uri TEXT NOT NULL,
  tags TEXT[] DEFAULT '{}',
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE task_asset_link_v2 (
  task_id BIGINT NOT NULL REFERENCES task_v2(id) ON DELETE CASCADE,
  asset_id BIGINT NOT NULL REFERENCES knowledge_asset_v2(id) ON DELETE CASCADE,
  PRIMARY KEY (task_id, asset_id)
);

CREATE TABLE asset_link_v2 (
  asset_id BIGINT NOT NULL REFERENCES knowledge_asset_v2(id) ON DELETE CASCADE,
  entity_type TEXT NOT NULL,
  entity_id BIGINT NOT NULL,
  role TEXT,
  metadata JSONB DEFAULT '{}',
  PRIMARY KEY (asset_id, entity_type, entity_id)
);

CREATE TABLE situation_snapshot_v2 (
  id BIGSERIAL PRIMARY KEY,
  incident_id BIGINT NOT NULL REFERENCES incident_v2(id) ON DELETE CASCADE,
  hazard_event_id BIGINT REFERENCES hazard_event_v2(id) ON DELETE SET NULL,
  generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  summary JSONB NOT NULL,
  source TEXT NOT NULL,
  metadata JSONB DEFAULT '{}'
);

CREATE TABLE audit_log_v2 (
  id BIGSERIAL PRIMARY KEY,
  mission_id BIGINT REFERENCES mission_v2(id) ON DELETE CASCADE,
  task_id BIGINT REFERENCES task_v2(id) ON DELETE SET NULL,
  platform_id BIGINT REFERENCES platform_v2(id) ON DELETE SET NULL,
  rescue_team_id BIGINT REFERENCES rescue_team_v2(id) ON DELETE SET NULL,
  route_plan_id BIGINT REFERENCES route_plan_v2(id) ON DELETE SET NULL,
  category TEXT NOT NULL,  -- constraint_hit / waiver / no_solution / replanning
  constraint_code TEXT,
  severity TEXT CHECK (severity IN ('info','warn','error')),
  detail JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ======================
-- 索引建议（需按需执行）
-- ======================
-- GIST on geometry columns (examples):
-- CREATE INDEX idx_obstacle_geom ON obstacle_v2 USING GIST (geometry);
-- CREATE INDEX idx_poi_geom ON priority_poi_v2 USING GIST (geometry);
-- CREATE INDEX idx_safe_site_geom ON safe_site_v2 USING GIST (geometry);
-- CREATE INDEX idx_route_seg_geom ON route_segment_v2 USING GIST (geometry);
-- CREATE INDEX idx_geo_entity_geom ON geo_entity_v2 USING GIST (geometry);
-- Time/index for logs:
-- CREATE INDEX idx_status_log_ts ON platform_status_log_v2(platform_id, ts);
-- CREATE INDEX idx_team_location_ts ON team_location_log_v2(team_id, ts);
-- Partitioning/TTL can be applied to *_log_v2, route_point_v2, audit_log_v2 per incident or time.
