-- 侦察方案记录表
-- 存储各种类型的方案（侦察方案、救援方案、疏散方案等）
-- 执行方式：psql -h 192.168.31.40 -U postgres -d emergency_agent -f sql/create_recon_plans_table.sql

CREATE TABLE IF NOT EXISTS recon_plans (
    -- 主键
    plan_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- 事件关联（可选，用于关联到具体事件）
    incident_id UUID,  -- 关联的事件ID（NULL表示独立方案）

    -- 方案类型
    plan_type VARCHAR(50) NOT NULL,  -- 方案类型：recon（侦察）、rescue（救援）、evacuation（疏散）等
    plan_subtype VARCHAR(50),  -- 子类型：batch_weather（批次天气侦察）、priority（优先级侦察）等

    -- 方案内容
    plan_title VARCHAR(200),  -- 方案标题
    plan_content TEXT NOT NULL,  -- 方案内容（纯文本/Markdown）
    plan_data JSONB,  -- 原始结构化数据（JSON格式）

    -- 灾情信息（快照）
    disaster_type VARCHAR(50),  -- 灾害类型：earthquake、flood、landslide等
    disaster_location JSONB,  -- 灾害位置：{"lon": 103.8, "lat": 31.66, "name": "茂县"}
    severity VARCHAR(20),  -- 严重程度：critical、high、medium、low

    -- 方案元数据
    device_count INTEGER DEFAULT 0,  -- 涉及设备数量
    target_count INTEGER DEFAULT 0,  -- 涉及目标数量
    estimated_duration INTEGER,  -- 预计执行时长（分钟）

    -- 生成信息
    llm_model VARCHAR(50),  -- 使用的LLM模型：glm-4.6、glm-4-flash等
    generation_time_ms INTEGER,  -- 生成耗时（毫秒）
    token_usage JSONB,  -- Token使用情况：{"prompt": 1000, "completion": 2000, "total": 3000}

    -- 审核状态
    status VARCHAR(20) DEFAULT 'draft',  -- 状态：draft（草稿）、approved（已批准）、rejected（已拒绝）、executed（已执行）
    approved_by VARCHAR(100),  -- 批准人
    approved_at TIMESTAMPTZ,  -- 批准时间

    -- 执行记录
    executed_by VARCHAR(100),  -- 执行人
    executed_at TIMESTAMPTZ,  -- 执行时间
    execution_result TEXT,  -- 执行结果

    -- 版本管理
    version INTEGER DEFAULT 1,  -- 方案版本号
    parent_plan_id UUID,  -- 父方案ID（用于修订版本）

    -- 审计字段
    created_by VARCHAR(100) NOT NULL,  -- 创建人
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,  -- 创建时间
    updated_by VARCHAR(100),  -- 更新人
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,  -- 更新时间

    -- 软删除
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_by VARCHAR(100),
    deleted_at TIMESTAMPTZ
);

-- 创建索引
CREATE INDEX idx_recon_plans_incident_id ON recon_plans(incident_id) WHERE NOT is_deleted;
CREATE INDEX idx_recon_plans_plan_type ON recon_plans(plan_type) WHERE NOT is_deleted;
CREATE INDEX idx_recon_plans_status ON recon_plans(status) WHERE NOT is_deleted;
CREATE INDEX idx_recon_plans_created_at ON recon_plans(created_at DESC) WHERE NOT is_deleted;
CREATE INDEX idx_recon_plans_disaster_type ON recon_plans(disaster_type) WHERE NOT is_deleted;

-- 创建灾害位置的GiST索引（用于地理位置查询）
-- 注意：需要先安装PostGIS扩展
-- CREATE EXTENSION IF NOT EXISTS postgis;
-- 如果需要地理位置查询，可以添加geometry字段和相应索引

-- 添加注释
COMMENT ON TABLE recon_plans IS '侦察和救援方案记录表';
COMMENT ON COLUMN recon_plans.plan_id IS '方案唯一ID';
COMMENT ON COLUMN recon_plans.incident_id IS '关联的事件ID';
COMMENT ON COLUMN recon_plans.plan_type IS '方案类型：recon/rescue/evacuation等';
COMMENT ON COLUMN recon_plans.plan_subtype IS '子类型：batch_weather/priority等';
COMMENT ON COLUMN recon_plans.plan_content IS '方案内容（纯文本/Markdown）';
COMMENT ON COLUMN recon_plans.plan_data IS '原始结构化数据（JSONB）';
COMMENT ON COLUMN recon_plans.status IS '状态：draft/approved/rejected/executed';
COMMENT ON COLUMN recon_plans.version IS '方案版本号，用于追踪修订历史';
COMMENT ON COLUMN recon_plans.parent_plan_id IS '父方案ID，用于关联修订版本';

-- 创建更新触发器（自动更新 updated_at）
CREATE OR REPLACE FUNCTION update_recon_plans_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_recon_plans_updated_at
    BEFORE UPDATE ON recon_plans
    FOR EACH ROW
    EXECUTE FUNCTION update_recon_plans_updated_at();

-- 示例查询
-- 1. 查询某个事件的所有侦察方案
-- SELECT * FROM recon_plans WHERE incident_id = 'xxx' AND plan_type = 'recon' AND NOT is_deleted ORDER BY created_at DESC;

-- 2. 查询待审批的方案
-- SELECT * FROM recon_plans WHERE status = 'draft' AND NOT is_deleted ORDER BY created_at DESC;

-- 3. 查询某个灾害类型的历史方案（用于案例学习）
-- SELECT * FROM recon_plans WHERE disaster_type = 'earthquake' AND status = 'approved' AND NOT is_deleted ORDER BY created_at DESC LIMIT 10;
