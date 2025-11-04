#!/usr/bin/env python3
"""直接测试SQL查询，不通过FastAPI"""
import asyncio
from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row

async def test_sql():
    # 从配置文件读取正确的连接信息
    pool = AsyncConnectionPool(
        "postgresql://postgres:postgres123@8.147.130.215:19532/emergency_agent",
        open=False
    )
    await pool.open()

    sql = (
        "SELECT id, name, target_type, hazard_level, priority, "
        "ST_X(location::geometry) as lon, ST_Y(location::geometry) as lat "
        "FROM operational.recon_priority_targets "
        "WHERE ST_DWithin(location::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s) "
        "ORDER BY priority DESC"
    )

    lon, lat, radius_meters = 103.85, 31.68, 5000.0

    print(f"SQL: {sql}")
    print(f"参数: lon={lon}, lat={lat}, radius_meters={radius_meters}")

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            print("执行查询...")
            await cur.execute(sql, (lon, lat, radius_meters))
            rows = await cur.fetchall()
            print(f"查询成功！返回{len(rows)}行")
            for row in rows[:3]:
                print(row)

    await pool.close()

if __name__ == "__main__":
    asyncio.run(test_sql())
