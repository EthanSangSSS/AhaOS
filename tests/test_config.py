from __future__ import annotations

from pathlib import Path
from ahaos.config import parse_simple_yaml, get_tag_keywords


def test_nested_delivery_max_daily_insights() -> None:
    yaml_text = """
    delivery:
      max_daily_insights: 7
    """
    parsed = parse_simple_yaml(yaml_text)
    assert parsed.get("delivery") == {"max_daily_insights": 7}


def test_nested_safety_require_evidence() -> None:
    yaml_text_true = """
    safety:
      require_evidence: true
    """
    yaml_text_false = """
    safety:
      require_evidence: false
    """
    parsed_true = parse_simple_yaml(yaml_text_true)
    parsed_false = parse_simple_yaml(yaml_text_false)
    
    assert parsed_true.get("safety") == {"require_evidence": True}
    assert parsed_false.get("safety") == {"require_evidence": False}


def test_list_parsing_for_tag_keywords() -> None:
    yaml_text = """
    tag_keywords:
      - pipeline
      - playbook
      - rollback
    """
    parsed = parse_simple_yaml(yaml_text)
    assert parsed.get("tag_keywords") == ["pipeline", "playbook", "rollback"]
    
    keywords = get_tag_keywords(parsed)
    assert "pipeline" in keywords
    assert "playbook" in keywords
    assert "rollback" in keywords
    assert "release" in keywords  # Default tag must be preserved
