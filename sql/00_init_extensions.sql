-- ============================================================================
-- PostGIS 扩展初始化脚本
-- ============================================================================
-- 说明: 此脚本必须在 operational.sql 之前执行
--       因为表结构依赖 PostGIS 的 geography 和 geometry 类型
--
-- 作用: 为 emergency_agent 数据库安装 PostGIS 空间数据库扩展
--       提供 ST_AsGeoJSON, ST_GeomFromGeoJSON, ST_X, ST_Y 等空间函数
-- ============================================================================

-- 创建 PostGIS 扩展（如果不存在）
CREATE EXTENSION IF NOT EXISTS postgis;

-- 验证扩展版本
SELECT PostGIS_Version();

-- 注释
COMMENT ON EXTENSION postgis IS '应急救援系统使用PostGIS存储和查询地理空间数据（实体位置、危险区域、任务位置等）';
