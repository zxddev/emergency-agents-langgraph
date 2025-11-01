from emergency_agents.intent.slot_normalizer import normalize_slots


def test_normalize_rescue_task_slots_basic():
    slots = {
        "task_type": "rescue",
        "location": "水磨镇",
        "latitude": "31.68",
        "longitude": "103.85",
        "extra_field": "ignored",
    }
    normalized = normalize_slots("rescue_task_generate", slots)
    assert normalized["mission_type"] == "前突救援"
    assert normalized["location_name"] == "水磨镇"
    assert normalized["coordinates"] == {"lat": 31.68, "lng": 103.85}
    assert "extra_field" not in normalized


def test_normalize_rescue_task_slots_coordinates_string():
    slots = {"mission_type": "rescue", "coordinates": "103.85,31.68"}
    normalized = normalize_slots("rescue_task_generate", slots)
    assert normalized["coordinates"] == {"lat": 31.68, "lng": 103.85}


def test_normalize_rescue_simulation_sets_flag():
    slots = {"mission_type": "rescue"}
    normalized = normalize_slots("rescue-simulation", slots)
    assert normalized["simulation_only"] is True
