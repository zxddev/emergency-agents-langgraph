import asyncio
import os
import sys

# Add src to path
sys.path.append("src")

from psycopg import AsyncConnection
from emergency_agents.config import AppConfig

async def main():
    # Load config (loads .env automatically via pydantic-settings if configured, 
    # but we might need to source it or rely on python-dotenv if AppConfig uses it)
    # AppConfig in this project seems to load from env.
    
    # Let's try to load manually if needed, but AppConfig usually handles it.
    try:
        cfg = AppConfig.load_from_env()
    except Exception as e:
        print(f"Error loading config: {e}")
        return

    dsn = cfg.postgres_dsn
    if not dsn:
        print("No POSTGRES_DSN found in environment.")
        return

    print(f"Connecting to database...")
    
    try:
        with open("sql/operational_v2_full.sql", "r") as f:
            sql = f.read()
    except FileNotFoundError:
        print("sql/operational_v2_full.sql not found.")
        return

    try:
        async with await AsyncConnection.connect(dsn) as aconn:
            async with aconn.cursor() as acur:
                print("Executing SQL script...")
                # Split commands by ; might be safer if the driver doesn't support multi-statement
                # But psycopg usually supports it.
                await acur.execute(sql)
                await aconn.commit()
                print("Schema applied successfully.")
    except Exception as e:
        print(f"Database error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
