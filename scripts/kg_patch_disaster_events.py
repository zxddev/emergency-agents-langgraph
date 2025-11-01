#!/usr/bin/env python3
"""Patch Neo4j disaster graph to ensure TRIGGERS/COMPOUNDS relationships exist."""

from __future__ import annotations

import os
from typing import Any, Dict, Iterable, Tuple

from neo4j import GraphDatabase, Session


URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER: str = os.getenv("NEO4J_USER", "neo4j")
PASSWORD: str = os.getenv("NEO4J_PASSWORD", "neo4j")

DISASTER_EVENTS: Tuple[Dict[str, Any], ...] = (
    {
        "key": "earthquake",
        "name": "地震",
        "severity": "catastrophic",
        "display_name": "特大地震",
    },
    {
        "key": "landslide",
        "name": "山体滑坡",
        "severity": "severe",
        "display_name": "山体滑坡",
    },
    {
        "key": "flood",
        "name": "洪水",
        "severity": "high",
        "display_name": "山洪泥石流",
    },
    {
        "key": "chemical_leak",
        "name": "化工泄漏",
        "severity": "severe",
        "display_name": "化工厂泄漏事故",
    },
    {
        "key": "fire",
        "name": "火灾",
        "severity": "high",
        "display_name": "火灾",
    },
)

TRIGGER_RELATIONS: Tuple[Dict[str, Any], ...] = (
    {
        "primary": "earthquake",
        "secondary": "landslide",
        "probability": 0.85,
        "delay_hours": 1.0,
        "condition": "magnitude>6.5 AND nearby_mountain",
        "severity_factor": 1.3,
    },
    {
        "primary": "earthquake",
        "secondary": "flood",
        "probability": 0.75,
        "delay_hours": 2.0,
        "condition": "magnitude>7.0 AND nearby_reservoir",
        "severity_factor": 1.5,
    },
    {
        "primary": "earthquake",
        "secondary": "chemical_leak",
        "probability": 0.60,
        "delay_hours": 3.0,
        "condition": "magnitude>7.0 AND nearby_chemical_plant",
        "severity_factor": 2.0,
    },
)

COMPOUND_RELATIONS: Tuple[Dict[str, Any], ...] = (
    {
        "source": "flood",
        "target": "chemical_leak",
        "compound_type": "toxic_spread",
        "severity_multiplier": 2.5,
        "description": "洪水扩散化工污染",
    },
)

REQUIRED_EQUIPMENT: Tuple[Dict[str, Any], ...] = (
    {
        "disaster": "flood",
        "items": (
            ("rescue_boat", 10.0, "high"),
        ),
    },
    {
        "disaster": "chemical_leak",
        "items": (
            ("hazmat_suit", 50.0, "critical"),
            ("gas_detector", 20.0, "high"),
        ),
    },
)


def apply_constraints(session: Session) -> None:
    statements: Tuple[str, ...] = (
        "CREATE CONSTRAINT disaster_event_name IF NOT EXISTS "
        "FOR (d:DisasterEvent) REQUIRE d.name IS UNIQUE",
        "CREATE CONSTRAINT equipment_id IF NOT EXISTS "
        "FOR (e:Equipment) REQUIRE e.id IS UNIQUE",
    )
    for cypher in statements:
        session.run(cypher)


def migrate_legacy_labels(session: Session) -> None:
    session.run(
        """
        MATCH (d:Disaster)
        WHERE NOT d:DisasterEvent
        SET d:DisasterEvent
        """
    )
    session.run(
        """
        MATCH ()-[r]->(d:Disaster)
        SET d:DisasterEvent
        """
    )
    session.run(
        """
        MATCH (d:DisasterEvent)
        REMOVE d:Disaster
        """
    )


def ensure_disaster_events(session: Session) -> None:
    for event in DISASTER_EVENTS:
        session.run(
            """
            MERGE (d:DisasterEvent {name: $name})
            SET d.type = $key,
                d.display_name = $display_name,
                d.severity = $severity
            """,
            event,
        )


def ensure_triggers(session: Session) -> None:
    for rel in TRIGGER_RELATIONS:
        session.run(
            """
            MATCH (p:DisasterEvent)
            WHERE coalesce(p.type, p.name) = $primary
            MATCH (s:DisasterEvent)
            WHERE coalesce(s.type, s.name) = $secondary
            MERGE (p)-[r:TRIGGERS]->(s)
            SET r.probability = $probability,
                r.delay_hours = $delay_hours,
                r.condition = $condition,
                r.severity_factor = $severity_factor
            """,
            rel,
        )


def ensure_compounds(session: Session) -> None:
    for rel in COMPOUND_RELATIONS:
        session.run(
            """
            MATCH (s:DisasterEvent)
            WHERE coalesce(s.type, s.name) = $source
            MATCH (t:DisasterEvent)
            WHERE coalesce(t.type, t.name) = $target
            MERGE (s)-[r:COMPOUNDS]->(t)
            SET r.type = $compound_type,
                r.severity_multiplier = $severity_multiplier,
                r.description = $description
            """,
            rel,
        )


def ensure_requires(session: Session) -> None:
    for definition in REQUIRED_EQUIPMENT:
        disaster: str = definition["disaster"]
        items: Iterable[Tuple[str, float, str]] = definition["items"]
        for equipment_id, quantity, urgency in items:
            session.run(
                """
                MATCH (d:DisasterEvent)
                WHERE coalesce(d.type, d.name) = $disaster
                MATCH (e:Equipment {id: $equipment_id})
                MERGE (d)-[r:REQUIRES]->(e)
                SET r.quantity = $quantity,
                    r.urgency = $urgency
                """,
                {
                    "disaster": disaster,
                    "equipment_id": equipment_id,
                    "quantity": quantity,
                    "urgency": urgency,
                },
            )


def summarize(session: Session) -> Dict[str, Any]:
    record = session.run(
        """
        CALL {
            MATCH (d:DisasterEvent)
            RETURN count(d) AS disasters
        }
        CALL {
            MATCH (:DisasterEvent)-[:TRIGGERS]->(:DisasterEvent)
            RETURN count(*) AS triggers
        }
        CALL {
            MATCH (:DisasterEvent)-[:COMPOUNDS]->(:DisasterEvent)
            RETURN count(*) AS compounds
        }
        CALL {
            MATCH (:DisasterEvent)-[:REQUIRES]->(:Equipment)
            RETURN count(*) AS requires
        }
        RETURN disasters, triggers, compounds, requires
        """
    ).single()
    assert record is not None
    return dict(record)


def main() -> None:
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    with driver.session() as session:
        print(f"Neo4j patch connected to {URI}")
        apply_constraints(session)
        migrate_legacy_labels(session)
        ensure_disaster_events(session)
        ensure_triggers(session)
        ensure_compounds(session)
        ensure_requires(session)
        metrics = summarize(session)
    driver.close()
    print(
        "Patch complete: "
        f"disasters={metrics['disasters']} "
        f"triggers={metrics['triggers']} "
        f"compounds={metrics['compounds']} "
        f"requires={metrics['requires']}"
    )


if __name__ == "__main__":
    main()
