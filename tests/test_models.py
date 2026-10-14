import json
from pathlib import Path
from simulator.models import ScenarioConfig

def test_fp001_yaml_has_expected_values():
    import yaml
    path=Path(__file__).parents[1]/"configs"/"fp001.yaml"
    cfg=yaml.safe_load(path.read_text(encoding="utf-8"))
    assert cfg["scenario_id"]=="FP-001"
    assert cfg["facility"]["critical_inference_mw"]+cfg["facility"]["fixed_auxiliary_mw"]+cfg["facility"]["deferrable_compute_mw"]==20
    assert cfg["grid_event"]["duration_minutes"]//cfg["grid_event"]["interval_minutes"]==12
    assert "planning baseline" in cfg["recovery"]["assumptions"][0]

def test_schema_documents_parse_as_json():
    root=Path(__file__).parents[1]/"contracts"
    for name in ("scenario.schema.json","result.schema.json"):
        json.loads((root/name).read_text(encoding="utf-8"))
