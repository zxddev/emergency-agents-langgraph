-- ============================================
-- Operational v2 Schema (PostgreSQL + PostGIS)
-- BIGSERIAL primary keys, business code columns
-- All tables under schema operational_v2; IAM under schema iam
-- ============================================

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS iam;
CREATE SCHEMA IF NOT EXISTS operational_v2;

SET search_path TO operational_v2, iam, public;

-- ================
-- IAM (users/roles)
-- ================
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
COMMENT ON TABLE iam.iam_user_v2 IS '用户表（权限/审计统一来源）';
COMMENT ON COLUMN iam.iam_user_v2.status IS 'active=可用, disabled=禁用';
COMMENT ON COLUMN iam.iam_user_v2.username IS '登录名/唯一用户标识';
COMMENT ON COLUMN iam.iam_user_v2.display_name IS '展示名';
COMMENT ON COLUMN iam.iam_user_v2.email IS '邮箱';
COMMENT ON COLUMN iam.iam_user_v2.phone IS '电话';
COMMENT ON COLUMN iam.iam_user_v2.created_at IS '创建时间';
COMMENT ON COLUMN iam.iam_user_v2.updated_at IS '更新时间';

CREATE TABLE iam.iam_permission_v2 (
  id BIGSERIAL PRIMARY KEY,
  resource_type TEXT NOT NULL CHECK (resource_type IN ('page','api','component')),
  resource_key TEXT NOT NULL,
  action TEXT NOT NULL CHECK (action IN ('view','edit','execute','approve')),
  description TEXT,
  UNIQUE (resource_type, resource_key, action)
);
COMMENT ON TABLE iam.iam_permission_v2 IS '权限项（页面/组件/API + action）';
COMMENT ON COLUMN iam.iam_permission_v2.resource_type IS 'page/api/component';
COMMENT ON COLUMN iam.iam_permission_v2.resource_key IS '前端路由/按钮标识/API路径';
COMMENT ON COLUMN iam.iam_permission_v2.action IS 'view/edit/execute/approve';
COMMENT ON COLUMN iam.iam_permission_v2.description IS '权限描述';
COMMENT ON COLUMN iam.iam_permission_v2.id IS '主键';

CREATE TABLE iam.iam_role_v2 (
  id BIGSERIAL PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  description TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE iam.iam_role_v2 IS '角色表';
COMMENT ON COLUMN iam.iam_role_v2.name IS '角色名称（唯一）';
COMMENT ON COLUMN iam.iam_role_v2.description IS '角色描述';
COMMENT ON COLUMN iam.iam_role_v2.created_at IS '创建时间';
COMMENT ON COLUMN iam.iam_role_v2.id IS '主键';

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

-- =====================
-- 事件 / 子灾害 / 任务
-- =====================
CREATE TABLE incident_v2 (
  id BIGSERIAL PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('active','closed','archived')),
  source TEXT NOT NULL, -- upper_command/manual/uav/sensor/external
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE incident_v2 IS '大事件（一次地震/洪水等）';
COMMENT ON COLUMN incident_v2.status IS 'active=处理中, closed=结束, archived=归档';
COMMENT ON COLUMN incident_v2.code IS '业务编号，如 INC20250214-0001';
COMMENT ON COLUMN incident_v2.source IS '来源：upper_command/manual/uav/sensor/external';
COMMENT ON COLUMN incident_v2.metadata IS '附加信息';
COMMENT ON COLUMN incident_v2.created_at IS '创建时间';
COMMENT ON COLUMN incident_v2.updated_at IS '更新时间';
COMMENT ON COLUMN incident_v2.id IS '主键';

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
COMMENT ON TABLE hazard_event_v2 IS '子灾害/二次灾害/局部险情';
COMMENT ON COLUMN hazard_event_v2.status IS 'active=进行中, monitoring=监测, resolved=已处置, archived=归档';
COMMENT ON COLUMN hazard_event_v2.code IS '业务编号，如 HEV20250214-0001';
COMMENT ON COLUMN hazard_event_v2.hazard_type IS '灾害类型：flood/fire/aftershock/...';
COMMENT ON COLUMN hazard_event_v2.time_window IS '生效时间窗';
COMMENT ON COLUMN hazard_event_v2.geometry IS '影响范围（几何）';
COMMENT ON COLUMN hazard_event_v2.source IS '来源';
COMMENT ON COLUMN hazard_event_v2.metadata IS '附加信息';
COMMENT ON COLUMN hazard_event_v2.created_at IS '创建时间';
COMMENT ON COLUMN hazard_event_v2.updated_at IS '更新时间';
COMMENT ON COLUMN hazard_event_v2.incident_id IS '关联大事件';
COMMENT ON COLUMN hazard_event_v2.id IS '主键';

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
COMMENT ON TABLE mission_v2 IS '行动批次/波次';
COMMENT ON COLUMN mission_v2.status IS 'planning=规划, in_progress=执行, completed=完成, failed=失败, cancelled=取消';
COMMENT ON COLUMN mission_v2.code IS '业务编号，如 MIS20250214-0001';
COMMENT ON COLUMN mission_v2.phase IS '阶段：preparation/transit/recon/rescue/evaluation';
COMMENT ON COLUMN mission_v2.metadata IS '附加信息';
COMMENT ON COLUMN mission_v2.created_at IS '创建时间';
COMMENT ON COLUMN mission_v2.updated_at IS '更新时间';
COMMENT ON COLUMN mission_v2.incident_id IS '关联大事件';
COMMENT ON COLUMN mission_v2.hazard_event_id IS '关联子灾害（可选）';
COMMENT ON COLUMN mission_v2.id IS '主键';

CREATE TABLE task_v2 (
  id BIGSERIAL PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  mission_id BIGINT NOT NULL REFERENCES mission_v2(id) ON DELETE CASCADE,
  hazard_event_id BIGINT REFERENCES hazard_event_v2(id) ON DELETE SET NULL,
  type TEXT NOT NULL, -- uav_recon/material_transport/rescue/...
  priority INT NOT NULL DEFAULT 3, -- 1 highest
  time_window TSRANGE,
  location geometry(Point,4326),
  area geometry(Geometry,4326),
  status TEXT NOT NULL CHECK (status IN ('pending','in_progress','completed','failed','cancelled')),
  demand JSONB NOT NULL DEFAULT '{}'::jsonb,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE task_v2 IS '任务（最小可分配单元）';
COMMENT ON COLUMN task_v2.status IS 'pending=待执行,in_progress=执行中,completed=完成,failed=失败,cancelled=取消';
COMMENT ON COLUMN task_v2.priority IS '1=最高优先';
COMMENT ON COLUMN task_v2.code IS '业务编号，如 TSK20250214-0001';
COMMENT ON COLUMN task_v2.type IS '任务类型：uav_recon/material_transport/rescue/...';
COMMENT ON COLUMN task_v2.time_window IS '任务时间窗（tsrange）';
COMMENT ON COLUMN task_v2.location IS '任务中心点（可选）';
COMMENT ON COLUMN task_v2.area IS '任务目标区域（多边形/线等）';
COMMENT ON COLUMN task_v2.demand IS '物资/装备/技能需求 JSON';
COMMENT ON COLUMN task_v2.metadata IS '附加信息';
COMMENT ON COLUMN task_v2.created_at IS '创建时间';
COMMENT ON COLUMN task_v2.updated_at IS '更新时间';
COMMENT ON COLUMN task_v2.mission_id IS '关联行动批次';
COMMENT ON COLUMN task_v2.hazard_event_id IS '关联子灾害（可选）';
COMMENT ON COLUMN task_v2.id IS '主键';

-- ================
-- 图层/实体/障碍等
-- ================
CREATE TABLE geo_layer_v2 (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT NOT NULL CHECK (category IN ('system','manual','hybrid')),
  access_scope TEXT NOT NULL CHECK (access_scope IN ('view','manage')),
  metadata JSONB DEFAULT '{}'
);
COMMENT ON TABLE geo_layer_v2 IS '地理图层/标绘分组';
COMMENT ON COLUMN geo_layer_v2.category IS 'system=系统层, manual=人工, hybrid=混合';
COMMENT ON COLUMN geo_layer_v2.access_scope IS 'view=只读, manage=可管理';
COMMENT ON COLUMN geo_layer_v2.metadata IS '附加信息';

CREATE TABLE geo_entity_v2 (
  id BIGSERIAL PRIMARY KEY,
  layer_id BIGINT REFERENCES geo_layer_v2(id) ON DELETE SET NULL,
  incident_id BIGINT REFERENCES incident_v2(id) ON DELETE CASCADE,
  type TEXT NOT NULL,
  geometry geometry(Geometry,4326) NOT NULL,
  properties JSONB DEFAULT '{}',
  source TEXT NOT NULL CHECK (source IN ('system','manual')),
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE geo_entity_v2 IS '地图实体/标绘（点/线/面等）';
COMMENT ON COLUMN geo_entity_v2.type IS '实体类型（自定义值，前端/业务约定）';
COMMENT ON COLUMN geo_entity_v2.source IS 'system/ manual';
COMMENT ON COLUMN geo_entity_v2.properties IS '属性 JSON';
COMMENT ON COLUMN geo_entity_v2.metadata IS '附加信息';
COMMENT ON COLUMN geo_entity_v2.created_at IS '创建时间';
COMMENT ON COLUMN geo_entity_v2.updated_at IS '更新时间';

CREATE TABLE obstacle_v2 (
  id BIGSERIAL PRIMARY KEY,
  incident_id BIGINT NOT NULL REFERENCES incident_v2(id) ON DELETE CASCADE,
  hazard_event_id BIGINT REFERENCES hazard_event_v2(id) ON DELETE SET NULL,
  type TEXT NOT NULL, -- road_blockage/flood/fire/no_fly/no_sail/hazard_zone...
  hardness TEXT NOT NULL CHECK (hardness IN ('hard','soft')),
  time_window TSRANGE,
  geometry geometry(Geometry,4326) NOT NULL,
  severity TEXT CHECK (severity IN ('low','medium','high','critical')),
  source TEXT NOT NULL,
  confidence NUMERIC CHECK (confidence BETWEEN 0 AND 1),
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE obstacle_v2 IS '障碍/封控/禁飞/风险区';
COMMENT ON COLUMN obstacle_v2.type IS 'road_blockage/flood/fire/no_fly/no_sail/hazard_zone 等';
COMMENT ON COLUMN obstacle_v2.hardness IS 'hard=硬阻断, soft=软惩罚';
COMMENT ON COLUMN obstacle_v2.severity IS 'low/medium/high/critical';
COMMENT ON COLUMN obstacle_v2.source IS 'sensor/uav/manual/external';
COMMENT ON COLUMN obstacle_v2.time_window IS '生效时间窗';
COMMENT ON COLUMN obstacle_v2.geometry IS '障碍几何（点/线/面）';
COMMENT ON COLUMN obstacle_v2.confidence IS '置信度 0-1';
COMMENT ON COLUMN obstacle_v2.metadata IS '附加信息';

CREATE TABLE obstacle_raster_v2 (
  id BIGSERIAL PRIMARY KEY,
  obstacle_id BIGINT NOT NULL REFERENCES obstacle_v2(id) ON DELETE CASCADE,
  uri TEXT NOT NULL,
  band_info JSONB DEFAULT '{}'
);
COMMENT ON TABLE obstacle_raster_v2 IS '障碍栅格/tiles 引用';
COMMENT ON COLUMN obstacle_raster_v2.uri IS '栅格路径或 tileset';
COMMENT ON COLUMN obstacle_raster_v2.band_info IS '波段/元数据';

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
COMMENT ON TABLE priority_poi_v2 IS '侦察/救援优先级目标点/区域';
COMMENT ON COLUMN priority_poi_v2.priority IS '1=最高优先';
COMMENT ON COLUMN priority_poi_v2.type IS '目标类别，如 bridge/hospital/trapped_cluster 等';
COMMENT ON COLUMN priority_poi_v2.geometry IS 'POI 几何（点/面）';
COMMENT ON COLUMN priority_poi_v2.time_window IS '时间窗';
COMMENT ON COLUMN priority_poi_v2.source IS '来源';
COMMENT ON COLUMN priority_poi_v2.confidence IS '置信度 0-1';
COMMENT ON COLUMN priority_poi_v2.metadata IS '附加信息';
COMMENT ON COLUMN priority_poi_v2.incident_id IS '关联大事件';
COMMENT ON COLUMN priority_poi_v2.hazard_event_id IS '关联子灾害（可选）';
COMMENT ON COLUMN priority_poi_v2.created_at IS '创建时间';
COMMENT ON COLUMN priority_poi_v2.updated_at IS '更新时间';
COMMENT ON COLUMN priority_poi_v2.id IS '主键';

CREATE TABLE task_poi_link_v2 (
  task_id BIGINT NOT NULL REFERENCES task_v2(id) ON DELETE CASCADE,
  poi_id BIGINT NOT NULL REFERENCES priority_poi_v2(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','in_progress','completed','skipped')),
  metadata JSONB DEFAULT '{}',
  PRIMARY KEY (task_id, poi_id)
);
COMMENT ON TABLE task_poi_link_v2 IS '任务与优先级POI的关联与完成状态';
COMMENT ON COLUMN task_poi_link_v2.status IS 'pending/in_progress/completed/skipped';
COMMENT ON COLUMN task_poi_link_v2.metadata IS '附加信息';
COMMENT ON COLUMN task_poi_link_v2.task_id IS '关联任务';
COMMENT ON COLUMN task_poi_link_v2.poi_id IS '关联 POI';

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
COMMENT ON COLUMN safe_site_v2.status IS 'available=可用,limited=受限,full=满员,closed=关闭';
COMMENT ON TABLE safe_site_v2 IS '安全/疏散/集结点';
COMMENT ON COLUMN safe_site_v2.category IS 'shelter=避难所,assembly=集结点,temporary_safe=临时安全点';
COMMENT ON COLUMN safe_site_v2.geometry IS '安全点几何（点/面）';
COMMENT ON COLUMN safe_site_v2.capacity IS '容量（人/车等）';
COMMENT ON COLUMN safe_site_v2.suitability IS '适用性评分';
COMMENT ON COLUMN safe_site_v2.source IS '来源：upper_command/manual/ai/field';
COMMENT ON COLUMN safe_site_v2.metadata IS '附加信息';
COMMENT ON COLUMN safe_site_v2.incident_id IS '关联大事件';
COMMENT ON COLUMN safe_site_v2.hazard_event_id IS '关联子灾害（可选）';
COMMENT ON COLUMN safe_site_v2.created_at IS '创建时间';
COMMENT ON COLUMN safe_site_v2.updated_at IS '更新时间';
COMMENT ON COLUMN safe_site_v2.id IS '主键';

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
COMMENT ON TABLE capability_profile_v2 IS '能力模板（几何/动力/环境/编组参数等）';
COMMENT ON COLUMN capability_profile_v2.kind IS 'ground/uav/usv/robot_dog/personnel';
COMMENT ON COLUMN capability_profile_v2.specs IS '能力 JSON（width/weight/turn_radius/max_slope/side_slope/wading/endurance/etc）';
COMMENT ON COLUMN capability_profile_v2.version IS '配置版本';
COMMENT ON COLUMN capability_profile_v2.name IS '能力模板名称';
COMMENT ON COLUMN capability_profile_v2.created_at IS '创建时间';
COMMENT ON COLUMN capability_profile_v2.id IS '主键';

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
COMMENT ON TABLE platform_v2 IS '内部平台（车辆/无人机/无人艇/机器人等）';
COMMENT ON COLUMN platform_v2.status IS 'available=可用,busy=执行,offline=离线,maintenance=维修';
COMMENT ON COLUMN platform_v2.home_location IS '常驻位置';
COMMENT ON COLUMN platform_v2.org_unit IS '所属单位';
COMMENT ON COLUMN platform_v2.plate_no IS '车牌/编号';
COMMENT ON COLUMN platform_v2.serial_no IS '序列号/机号';
COMMENT ON COLUMN platform_v2.metadata IS '附加信息（支持扩展字段）';
COMMENT ON COLUMN platform_v2.capability_profile_id IS '关联能力模板';
COMMENT ON COLUMN platform_v2.created_at IS '创建时间';
COMMENT ON COLUMN platform_v2.updated_at IS '更新时间';
COMMENT ON COLUMN platform_v2.id IS '主键';

CREATE TABLE platform_capability_v2 (
  platform_id BIGINT PRIMARY KEY REFERENCES platform_v2(id) ON DELETE CASCADE,
  overrides JSONB DEFAULT '{}',
  effective_profile JSONB,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE platform_capability_v2 IS '平台能力（基于模板的覆盖/合并结果）';
COMMENT ON COLUMN platform_capability_v2.overrides IS '覆盖的字段';
COMMENT ON COLUMN platform_capability_v2.effective_profile IS '合并后的实际能力';
COMMENT ON COLUMN platform_capability_v2.updated_at IS '更新时间';
COMMENT ON COLUMN platform_capability_v2.platform_id IS '关联平台（主键）';

CREATE TABLE equipment_loadout_v2 (
  id BIGSERIAL PRIMARY KEY,
  platform_id BIGINT NOT NULL REFERENCES platform_v2(id) ON DELETE CASCADE,
  item_id TEXT NOT NULL,
  qty NUMERIC,
  metadata JSONB DEFAULT '{}',
  UNIQUE (platform_id, item_id)
);
COMMENT ON TABLE equipment_loadout_v2 IS '平台装备/物资/技能清单';
COMMENT ON COLUMN equipment_loadout_v2.platform_id IS '关联平台';
COMMENT ON COLUMN equipment_loadout_v2.item_id IS '物资/装备/技能标识';
COMMENT ON COLUMN equipment_loadout_v2.qty IS '数量';
COMMENT ON COLUMN equipment_loadout_v2.metadata IS '附加信息';
COMMENT ON COLUMN equipment_loadout_v2.id IS '主键';

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
COMMENT ON TABLE rescue_team_v2 IS '外部/内部救援队伍（人/编组）';
COMMENT ON COLUMN rescue_team_v2.status IS 'available/busy/offline';
COMMENT ON COLUMN rescue_team_v2.org IS '所属机构';
COMMENT ON COLUMN rescue_team_v2.home_base IS '常驻基地';
COMMENT ON COLUMN rescue_team_v2.contact IS '联系方式';
COMMENT ON COLUMN rescue_team_v2.capability_profile_id IS '关联能力模板';
COMMENT ON COLUMN rescue_team_v2.location IS '最近位置';
COMMENT ON COLUMN rescue_team_v2.metadata IS '附加信息';
COMMENT ON COLUMN rescue_team_v2.created_at IS '创建时间';
COMMENT ON COLUMN rescue_team_v2.updated_at IS '更新时间';
COMMENT ON COLUMN rescue_team_v2.id IS '主键';

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
COMMENT ON TABLE team_member_v2 IS '队伍成员或关联的平台成员';
COMMENT ON COLUMN team_member_v2.person_name IS '成员姓名';
COMMENT ON COLUMN team_member_v2.role IS '驾驶/指挥/侦察/医护等';
COMMENT ON COLUMN team_member_v2.contact IS '联系方式';
COMMENT ON COLUMN team_member_v2.metadata IS '附加信息';
COMMENT ON COLUMN team_member_v2.team_id IS '关联队伍';
COMMENT ON COLUMN team_member_v2.platform_id IS '关联平台（成员为设备时）';
COMMENT ON COLUMN team_member_v2.id IS '主键';

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
COMMENT ON TABLE team_platform_v2 IS '队伍声明的设备/能力（可挂平台模板）';
COMMENT ON COLUMN team_platform_v2.name IS '设备名称（未挂平台时）';
COMMENT ON COLUMN team_platform_v2.skills IS '特长标签';
COMMENT ON COLUMN team_platform_v2.contact IS '联系方式';
COMMENT ON COLUMN team_platform_v2.metadata IS '附加信息';
COMMENT ON COLUMN team_platform_v2.team_id IS '关联队伍';
COMMENT ON COLUMN team_platform_v2.platform_id IS '关联平台（可选）';
COMMENT ON COLUMN team_platform_v2.capability_profile_id IS '关联能力模板';
COMMENT ON COLUMN team_platform_v2.id IS '主键';

-- ======================
-- 路径/候选/指派/调度
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
COMMENT ON TABLE route_plan_v2 IS '路径规划主表，内/外部执行二选一，可关联安全点';
COMMENT ON COLUMN route_plan_v2.status IS 'draft=草稿,active=执行中,completed=完成,failed=失败,cancelled=取消';
COMMENT ON COLUMN route_plan_v2.code IS '业务编号，如 RPL20250214-0001';
COMMENT ON COLUMN route_plan_v2.cost IS '总成本（可含能耗/风险等）';
COMMENT ON COLUMN route_plan_v2.risk IS '风险/豁免信息 JSON';
COMMENT ON COLUMN route_plan_v2.safe_site_id IS '关联安全/疏散点';
COMMENT ON COLUMN route_plan_v2.mission_id IS '关联行动批次';
COMMENT ON COLUMN route_plan_v2.platform_id IS '关联内部平台（内执行时）';
COMMENT ON COLUMN route_plan_v2.rescue_team_id IS '关联外部队伍（外执行时）';
COMMENT ON COLUMN route_plan_v2.task_id IS '关联任务';
COMMENT ON COLUMN route_plan_v2.created_at IS '创建时间';
COMMENT ON COLUMN route_plan_v2.updated_at IS '更新时间';

-- 安全点选择记录（放在平台/队伍定义之后，避免外键缺表）
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
COMMENT ON TABLE safe_site_selection_v2 IS '任务/平台/队伍与安全点的推荐/选择记录';
COMMENT ON COLUMN safe_site_selection_v2.status IS 'proposed=推荐,accepted=接受,rejected=拒绝';
COMMENT ON COLUMN safe_site_selection_v2.selection_reason IS '推荐/选择理由';
COMMENT ON COLUMN safe_site_selection_v2.metadata IS '附加信息';
COMMENT ON COLUMN safe_site_selection_v2.mission_id IS '关联行动批次';
COMMENT ON COLUMN safe_site_selection_v2.task_id IS '关联任务（可选）';
COMMENT ON COLUMN safe_site_selection_v2.platform_id IS '关联平台（内部）';
COMMENT ON COLUMN safe_site_selection_v2.rescue_team_id IS '关联外部队伍';
COMMENT ON COLUMN safe_site_selection_v2.safe_site_id IS '关联安全点';
COMMENT ON COLUMN safe_site_selection_v2.created_at IS '创建时间';
COMMENT ON COLUMN safe_site_selection_v2.updated_at IS '更新时间';
COMMENT ON COLUMN safe_site_selection_v2.id IS '主键';
COMMENT ON COLUMN safe_site_selection_v2.status IS 'proposed=推荐,accepted=接受,rejected=拒绝';

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
COMMENT ON TABLE route_candidate_v2 IS '路线候选方案';
COMMENT ON COLUMN route_candidate_v2.status IS 'proposed=候选,selected=选中,rejected=拒绝';
COMMENT ON COLUMN route_candidate_v2.cost IS '候选成本';
COMMENT ON COLUMN route_candidate_v2.risk IS '候选风险信息';
COMMENT ON COLUMN route_candidate_v2.geometry IS '候选整条线（可选）';
COMMENT ON COLUMN route_candidate_v2.metadata IS '附加信息';
COMMENT ON COLUMN route_candidate_v2.route_plan_id IS '关联主路线';
COMMENT ON COLUMN route_candidate_v2.rank IS '候选顺序/优先';
COMMENT ON COLUMN route_candidate_v2.created_at IS '创建时间';
COMMENT ON COLUMN route_candidate_v2.updated_at IS '更新时间';
COMMENT ON COLUMN route_candidate_v2.id IS '主键';

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
COMMENT ON TABLE route_segment_v2 IS '路线分段（支持通道 channel）';
COMMENT ON COLUMN route_segment_v2.channel IS 'ground/air/water/foot';
COMMENT ON COLUMN route_segment_v2.distance_km IS '分段距离（公里）';
COMMENT ON COLUMN route_segment_v2.eta_hours IS '分段预计时间（小时）';
COMMENT ON COLUMN route_segment_v2.metrics IS '分段指标（迭代数/节点数等）';
COMMENT ON COLUMN route_segment_v2.start_point IS '分段起点';
COMMENT ON COLUMN route_segment_v2.end_point IS '分段终点';
COMMENT ON COLUMN route_segment_v2.geometry IS '分段几何线';
COMMENT ON COLUMN route_segment_v2.route_plan_id IS '关联路线';
COMMENT ON COLUMN route_segment_v2.seq IS '分段序号';
COMMENT ON COLUMN route_segment_v2.id IS '主键';

CREATE TABLE route_point_v2 (
  id BIGSERIAL PRIMARY KEY,
  segment_id BIGINT NOT NULL REFERENCES route_segment_v2(id) ON DELETE CASCADE,
  seq INT NOT NULL,
  pt geometry(Point,4326)
);
COMMENT ON TABLE route_point_v2 IS '路线点（可按需分区/外部存储）';
COMMENT ON COLUMN route_point_v2.seq IS '序号';
COMMENT ON COLUMN route_point_v2.pt IS '点坐标';

CREATE TABLE cost_matrix_cache_v2 (
  id BIGSERIAL PRIMARY KEY,
  mission_id BIGINT NOT NULL REFERENCES mission_v2(id) ON DELETE CASCADE,
  computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  matrix JSONB NOT NULL,
  metadata JSONB DEFAULT '{}'
);
COMMENT ON TABLE cost_matrix_cache_v2 IS '调度成本矩阵缓存（可配合稀疏边表使用）';
COMMENT ON COLUMN cost_matrix_cache_v2.matrix IS '矩阵 JSON，可搭配 edge 表审计';
COMMENT ON COLUMN cost_matrix_cache_v2.metadata IS '附加信息';
COMMENT ON COLUMN cost_matrix_cache_v2.mission_id IS '关联行动批次';
COMMENT ON COLUMN cost_matrix_cache_v2.computed_at IS '生成时间';
COMMENT ON COLUMN cost_matrix_cache_v2.id IS '主键';

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
COMMENT ON TABLE cost_matrix_edge_v2 IS '调度成本稀疏边表，便于审计/过滤原因';
COMMENT ON COLUMN cost_matrix_edge_v2.feasible IS '可行性（false 表示过滤）';
COMMENT ON COLUMN cost_matrix_edge_v2.reason IS '不可行/高成本原因';
COMMENT ON COLUMN cost_matrix_edge_v2.metadata IS '附加信息';
COMMENT ON COLUMN cost_matrix_edge_v2.cache_id IS '关联成本缓存';
COMMENT ON COLUMN cost_matrix_edge_v2.platform_id IS '关联平台';
COMMENT ON COLUMN cost_matrix_edge_v2.task_id IS '关联任务';
COMMENT ON COLUMN cost_matrix_edge_v2.cost IS '成本';
COMMENT ON COLUMN cost_matrix_edge_v2.id IS '主键';

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
COMMENT ON TABLE task_assignment_v2 IS '任务指派（内外部执行二选一），含审批/负责人';
COMMENT ON COLUMN task_assignment_v2.status IS 'assigned=指派,accepted=接受,rejected=拒绝,completed=完成,failed=失败';
COMMENT ON COLUMN task_assignment_v2.approval_status IS 'pending=待审,approved=通过,rejected=拒绝';
COMMENT ON COLUMN task_assignment_v2.task_id IS '关联任务';
COMMENT ON COLUMN task_assignment_v2.platform_id IS '关联内部平台';
COMMENT ON COLUMN task_assignment_v2.rescue_team_id IS '关联外部队伍';
COMMENT ON COLUMN task_assignment_v2.eta_hours IS '预计时间（小时）';
COMMENT ON COLUMN task_assignment_v2.route_plan_id IS '关联路线方案';
COMMENT ON COLUMN task_assignment_v2.cost IS '指派成本';
COMMENT ON COLUMN task_assignment_v2.executor_type IS 'internal_platform / external_team';
COMMENT ON COLUMN task_assignment_v2.responsible_user_id IS '负责人（用户）';
COMMENT ON COLUMN task_assignment_v2.approved_by IS '审批人';
COMMENT ON COLUMN task_assignment_v2.approved_at IS '审批时间';
COMMENT ON COLUMN task_assignment_v2.created_at IS '创建时间';
COMMENT ON COLUMN task_assignment_v2.updated_at IS '更新时间';
COMMENT ON COLUMN task_assignment_v2.id IS '主键';

-- ======================
-- 观测/告警/日志/遥测
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
COMMENT ON TABLE observation_v2 IS '观测/情报归档（障碍/POI 的原始证据）';
COMMENT ON COLUMN observation_v2.source IS 'uav/sensor/manual/external';
COMMENT ON COLUMN observation_v2.obs_type IS 'damage/flood/fire/blocked_road/...';
COMMENT ON COLUMN observation_v2.confidence IS '置信度 0-1';
COMMENT ON COLUMN observation_v2.time_window IS '观测时间窗';
COMMENT ON COLUMN observation_v2.reporter_user_id IS '上报人（用户）';
COMMENT ON COLUMN observation_v2.reporter_platform_id IS '上报设备';
COMMENT ON COLUMN observation_v2.metadata IS '附加信息';
COMMENT ON COLUMN observation_v2.incident_id IS '关联大事件';
COMMENT ON COLUMN observation_v2.hazard_event_id IS '关联子灾害（可选）';
COMMENT ON COLUMN observation_v2.created_at IS '创建时间';
COMMENT ON COLUMN observation_v2.id IS '主键';

CREATE TABLE obstacle_observation_v2 (
  obstacle_id BIGINT NOT NULL REFERENCES obstacle_v2(id) ON DELETE CASCADE,
  observation_id BIGINT NOT NULL REFERENCES observation_v2(id) ON DELETE CASCADE,
  PRIMARY KEY (obstacle_id, observation_id)
);
COMMENT ON TABLE obstacle_observation_v2 IS '障碍与观测的关联';

CREATE TABLE poi_observation_v2 (
  poi_id BIGINT NOT NULL REFERENCES priority_poi_v2(id) ON DELETE CASCADE,
  observation_id BIGINT NOT NULL REFERENCES observation_v2(id) ON DELETE CASCADE,
  PRIMARY KEY (poi_id, observation_id)
);
COMMENT ON TABLE poi_observation_v2 IS 'POI 与观测的关联';

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
COMMENT ON TABLE platform_status_log_v2 IS '设备状态/健康日志';
COMMENT ON COLUMN platform_status_log_v2.status IS 'available=可用,busy=执行,offline=离线,maintenance=维修';
COMMENT ON COLUMN platform_status_log_v2.health IS 'ok/warn/fail 等健康状态';
COMMENT ON COLUMN platform_status_log_v2.comm_link IS '通信链路状态';
COMMENT ON COLUMN platform_status_log_v2.metrics IS '附加指标（JSON）';
COMMENT ON COLUMN platform_status_log_v2.ts IS '时间戳';
COMMENT ON COLUMN platform_status_log_v2.battery_pct IS '电量百分比';
COMMENT ON COLUMN platform_status_log_v2.fuel_level IS '燃料/电量';
COMMENT ON COLUMN platform_status_log_v2.location IS '位置';
COMMENT ON COLUMN platform_status_log_v2.platform_id IS '关联平台';
COMMENT ON COLUMN platform_status_log_v2.id IS '主键';

CREATE TABLE platform_telemetry_v2 (
  id BIGSERIAL PRIMARY KEY,
  platform_id BIGINT NOT NULL REFERENCES platform_v2(id) ON DELETE CASCADE,
  ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  location geometry(Point,4326),
  speed NUMERIC,
  heading NUMERIC,
  metrics JSONB DEFAULT '{}'
);
COMMENT ON TABLE platform_telemetry_v2 IS '设备遥测（位置/速度/航向/附加指标）';
COMMENT ON COLUMN platform_telemetry_v2.metrics IS '附加指标（JSON）';
COMMENT ON COLUMN platform_telemetry_v2.location IS '位置';
COMMENT ON COLUMN platform_telemetry_v2.speed IS '速度';
COMMENT ON COLUMN platform_telemetry_v2.heading IS '航向';
COMMENT ON COLUMN platform_telemetry_v2.platform_id IS '关联平台';
COMMENT ON COLUMN platform_telemetry_v2.ts IS '时间戳';
COMMENT ON COLUMN platform_telemetry_v2.id IS '主键';

CREATE TABLE team_location_log_v2 (
  id BIGSERIAL PRIMARY KEY,
  team_id BIGINT NOT NULL REFERENCES rescue_team_v2(id) ON DELETE CASCADE,
  ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  location geometry(Point,4326),
  metadata JSONB DEFAULT '{}'
);
COMMENT ON TABLE team_location_log_v2 IS '队伍位置轨迹日志';
COMMENT ON COLUMN team_location_log_v2.team_id IS '关联队伍';
COMMENT ON COLUMN team_location_log_v2.ts IS '时间戳';
COMMENT ON COLUMN team_location_log_v2.location IS '位置';
COMMENT ON COLUMN team_location_log_v2.metadata IS '附加信息';
COMMENT ON COLUMN team_location_log_v2.id IS '主键';

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
COMMENT ON TABLE alert_rule_v2 IS '告警规则，定义触发条件与通知目标';
COMMENT ON COLUMN alert_rule_v2.action IS 'notify/push 等通知方式';
COMMENT ON COLUMN alert_rule_v2.trigger IS '触发条件 JSON';
COMMENT ON COLUMN alert_rule_v2.target IS '通知目标 JSON（用户/角色/队伍/平台）';
COMMENT ON COLUMN alert_rule_v2.incident_id IS '关联大事件';
COMMENT ON COLUMN alert_rule_v2.enabled IS '是否启用';
COMMENT ON COLUMN alert_rule_v2.created_at IS '创建时间';
COMMENT ON COLUMN alert_rule_v2.id IS '主键';

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
COMMENT ON TABLE alert_event_v2 IS '告警触发记录';
COMMENT ON COLUMN alert_event_v2.status IS 'pending=待发送,sent=已发送,failed=失败';
COMMENT ON COLUMN alert_event_v2.incident_id IS '关联大事件';
COMMENT ON COLUMN alert_event_v2.hazard_event_id IS '关联子灾害（可选）';
COMMENT ON COLUMN alert_event_v2.rule_id IS '关联规则（可空）';
COMMENT ON COLUMN alert_event_v2.triggered_by IS '触发源 JSON';
COMMENT ON COLUMN alert_event_v2.targets IS '实际通知目标 JSON';
COMMENT ON COLUMN alert_event_v2.sent_at IS '发送时间';
COMMENT ON COLUMN alert_event_v2.metadata IS '附加信息';
COMMENT ON COLUMN alert_event_v2.created_at IS '创建时间';
COMMENT ON COLUMN alert_event_v2.id IS '主键';

-- ======================
-- 知识资产 / 快照 / 审计
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
COMMENT ON TABLE knowledge_asset_v2 IS '知识资产：图像/文档/案例/规范等';
COMMENT ON COLUMN knowledge_asset_v2.kind IS 'image/document/case/spec';
COMMENT ON COLUMN knowledge_asset_v2.uri IS '存储路径/对象ID';
COMMENT ON COLUMN knowledge_asset_v2.tags IS '标签数组';
COMMENT ON COLUMN knowledge_asset_v2.metadata IS '附加信息（EXIF/OCR/摘要等）';
COMMENT ON COLUMN knowledge_asset_v2.title IS '标题';
COMMENT ON COLUMN knowledge_asset_v2.created_at IS '创建时间';
COMMENT ON COLUMN knowledge_asset_v2.id IS '主键';

CREATE TABLE task_asset_link_v2 (
  task_id BIGINT NOT NULL REFERENCES task_v2(id) ON DELETE CASCADE,
  asset_id BIGINT NOT NULL REFERENCES knowledge_asset_v2(id) ON DELETE CASCADE,
  PRIMARY KEY (task_id, asset_id)
);
COMMENT ON TABLE task_asset_link_v2 IS '任务与资产关联';
COMMENT ON COLUMN task_asset_link_v2.task_id IS '关联任务';
COMMENT ON COLUMN task_asset_link_v2.asset_id IS '关联资产';
COMMENT ON COLUMN task_asset_link_v2.task_id IS '关联任务';
COMMENT ON COLUMN task_asset_link_v2.asset_id IS '关联资产';

CREATE TABLE asset_link_v2 (
  asset_id BIGINT NOT NULL REFERENCES knowledge_asset_v2(id) ON DELETE CASCADE,
  entity_type TEXT NOT NULL,
  entity_id BIGINT NOT NULL,
  role TEXT,
  metadata JSONB DEFAULT '{}',
  PRIMARY KEY (asset_id, entity_type, entity_id)
);
COMMENT ON TABLE asset_link_v2 IS '资产通用关联表，可挂 task/incident/hazard/platform/obstacle/observation 等';
COMMENT ON COLUMN asset_link_v2.entity_type IS '关联实体类型';
COMMENT ON COLUMN asset_link_v2.entity_id IS '关联实体ID';
COMMENT ON COLUMN asset_link_v2.role IS '关联角色：evidence/spec/after_action_report 等';
COMMENT ON COLUMN asset_link_v2.metadata IS '附加信息';

CREATE TABLE situation_snapshot_v2 (
  id BIGSERIAL PRIMARY KEY,
  incident_id BIGINT NOT NULL REFERENCES incident_v2(id) ON DELETE CASCADE,
  hazard_event_id BIGINT REFERENCES hazard_event_v2(id) ON DELETE SET NULL,
  generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  summary JSONB NOT NULL,
  source TEXT NOT NULL,
  metadata JSONB DEFAULT '{}'
);
COMMENT ON TABLE situation_snapshot_v2 IS '态势快照/汇总（上报/复盘）';
COMMENT ON COLUMN situation_snapshot_v2.summary IS '汇总 JSON（关键障碍/POI/任务进度/平台状态摘要等）';
COMMENT ON COLUMN situation_snapshot_v2.source IS 'system/ai/manual';
COMMENT ON COLUMN situation_snapshot_v2.incident_id IS '关联大事件';
COMMENT ON COLUMN situation_snapshot_v2.hazard_event_id IS '关联子灾害（可选）';
COMMENT ON COLUMN situation_snapshot_v2.generated_at IS '生成时间';
COMMENT ON COLUMN situation_snapshot_v2.metadata IS '附加信息';
COMMENT ON COLUMN situation_snapshot_v2.id IS '主键';

CREATE TABLE audit_log_v2 (
  id BIGSERIAL PRIMARY KEY,
  mission_id BIGINT REFERENCES mission_v2(id) ON DELETE CASCADE,
  task_id BIGINT REFERENCES task_v2(id) ON DELETE SET NULL,
  platform_id BIGINT REFERENCES platform_v2(id) ON DELETE SET NULL,
  rescue_team_id BIGINT REFERENCES rescue_team_v2(id) ON DELETE SET NULL,
  route_plan_id BIGINT REFERENCES route_plan_v2(id) ON DELETE SET NULL,
  category TEXT NOT NULL,
  constraint_code TEXT,
  severity TEXT CHECK (severity IN ('info','warn','error')),
  detail JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE audit_log_v2 IS '审计日志：约束命中/豁免/无解/重规划';
COMMENT ON COLUMN audit_log_v2.category IS 'constraint_hit/waiver/no_solution/replanning';
COMMENT ON COLUMN audit_log_v2.severity IS 'info/warn/error';
COMMENT ON COLUMN audit_log_v2.detail IS '详细上下文（JSON）';
COMMENT ON COLUMN audit_log_v2.mission_id IS '关联行动批次';
COMMENT ON COLUMN audit_log_v2.task_id IS '关联任务';
COMMENT ON COLUMN audit_log_v2.platform_id IS '关联平台';
COMMENT ON COLUMN audit_log_v2.rescue_team_id IS '关联外部队伍';
COMMENT ON COLUMN audit_log_v2.route_plan_id IS '关联路线';
COMMENT ON COLUMN audit_log_v2.created_at IS '记录时间';
COMMENT ON COLUMN audit_log_v2.id IS '主键';

-- ======================
-- 索引建议（需按需执行）
-- ======================
-- Geometry GIST:
-- CREATE INDEX idx_obstacle_geom ON obstacle_v2 USING GIST (geometry);
-- CREATE INDEX idx_poi_geom ON priority_poi_v2 USING GIST (geometry);
-- CREATE INDEX idx_safe_site_geom ON safe_site_v2 USING GIST (geometry);
-- CREATE INDEX idx_geo_entity_geom ON geo_entity_v2 USING GIST (geometry);
-- CREATE INDEX idx_route_seg_geom ON route_segment_v2 USING GIST (geometry);
-- CREATE INDEX idx_route_candidate_geom ON route_candidate_v2 USING GIST (geometry);
-- Time/Status BTREE:
-- CREATE INDEX idx_status_log_ts ON platform_status_log_v2(platform_id, ts);
-- CREATE INDEX idx_team_location_ts ON team_location_log_v2(team_id, ts);
-- CREATE INDEX idx_cost_cache_mission ON cost_matrix_cache_v2(mission_id, computed_at);
-- Partitioning/TTL: apply to *_log_v2, route_point_v2, audit_log_v2, situation_snapshot_v2 as needed.
