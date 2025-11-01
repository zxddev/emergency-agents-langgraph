-- Scout 集成测试数据
-- 所有测试设备 ID 以 TEST- 开头，方便自动清理
-- 用于测试 device_selection, recon_route_planning, sensor_payload_assignment 节点

-- 测试无人机设备
INSERT INTO operational.device (id, name, device_type, env_type, model, vendor, is_virtual, is_recon, deleted_at)
VALUES
    ('TEST-UAV-001', '测试大疆M30', 'UAV', 'air', 'M30', 'DJI', 0, true, NULL),
    ('TEST-UAV-002', '测试大疆M300', 'UAV', 'air', 'M300', 'DJI', 0, true, NULL)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    device_type = EXCLUDED.device_type,
    env_type = EXCLUDED.env_type,
    model = EXCLUDED.model,
    vendor = EXCLUDED.vendor,
    is_virtual = EXCLUDED.is_virtual,
    is_recon = EXCLUDED.is_recon,
    deleted_at = EXCLUDED.deleted_at;

-- 测试机器狗设备
INSERT INTO operational.device (id, name, device_type, env_type, model, vendor, is_virtual, is_recon, deleted_at)
VALUES
    ('TEST-UGV-001', '测试宇树Go2', 'ROBOTDOG', 'land', 'Go2', 'Unitree', 0, true, NULL),
    ('TEST-UGV-002', '测试波士顿动力Spot', 'ROBOTDOG', 'land', 'Spot', 'Boston Dynamics', 0, false, NULL)
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    device_type = EXCLUDED.device_type,
    env_type = EXCLUDED.env_type,
    model = EXCLUDED.model,
    vendor = EXCLUDED.vendor,
    is_virtual = EXCLUDED.is_virtual,
    is_recon = EXCLUDED.is_recon,
    deleted_at = EXCLUDED.deleted_at;

-- 测试设备能力（device_capability 表）
INSERT INTO operational.device_capability (device_id, capability)
VALUES
    ('TEST-UAV-001', 'aerial_recon'),
    ('TEST-UAV-001', 'thermal_imaging'),
    ('TEST-UAV-001', 'gas_detection'),
    ('TEST-UAV-002', 'aerial_recon'),
    ('TEST-UAV-002', 'mapping'),
    ('TEST-UGV-001', 'ground_patrol'),
    ('TEST-UGV-001', 'obstacle_detection'),
    ('TEST-UGV-002', 'ground_patrol')
ON CONFLICT (device_id, capability) DO NOTHING;

-- 说明：
-- 1. TEST-UAV-001: 在线侦察无人机，具备热成像和气体检测能力
-- 2. TEST-UAV-002: 在线侦察无人机，具备地图测绘能力
-- 3. TEST-UGV-001: 在线侦察机器狗，具备地面巡逻能力
-- 4. TEST-UGV-002: 离线机器狗（is_recon=false），用于测试设备过滤逻辑

-- 清理命令（自动化测试结束后执行）：
-- DELETE FROM operational.device_capability WHERE device_id LIKE 'TEST-%';
-- DELETE FROM operational.device WHERE id LIKE 'TEST-%';
