-- 侦察设备测试数据
-- 用途：为Python端侦察流程测试提供设备数据
-- 执行方式：在operational数据库中执行此SQL

-- 插入测试设备到device表
INSERT INTO operational.device (id, name, device_type, weather_capability, status, created_at, updated_at)
VALUES
    (9001, '大疆 Mavic 3E', 'UAV', '全天候', 'online', NOW(), NOW()),
    (9002, '大疆 Matrice 30T', 'UAV', '全天候', 'online', NOW(), NOW()),
    (9003, '道通 EVO Max 4T', 'UAV', '晴天', 'online', NOW(), NOW())
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    device_type = EXCLUDED.device_type,
    weather_capability = EXCLUDED.weather_capability,
    status = EXCLUDED.status,
    updated_at = NOW();

-- 将设备标记为已选中（is_selected=1）
INSERT INTO operational.car_device_select (device_id, is_selected, created_at, updated_at)
VALUES
    (9001, 1, NOW(), NOW()),
    (9002, 1, NOW(), NOW()),
    (9003, 1, NOW(), NOW())
ON CONFLICT (device_id) DO UPDATE SET
    is_selected = 1,
    updated_at = NOW();

-- 验证数据插入成功
SELECT
    d.id::text AS device_id,
    d.name,
    d.device_type,
    COALESCE(d.weather_capability, '') AS weather_capability,
    d.status,
    c.is_selected
FROM operational.device d
JOIN operational.car_device_select c ON d.id = c.device_id
WHERE c.is_selected = 1
ORDER BY d.id;
