from types import SimpleNamespace

from scanbox.adapters.yara import YaraAdapter


def test_yara_detection_uses_meta_not_legacy_strings_shape() -> None:
    fake_match = SimpleNamespace(
        rule="scanbox_test_rule",
        namespace="default",
        tags=["suspicious"],
        meta={
            "title": "Test rule",
            "description": "Test description",
            "severity": "medium",
            "confidence": "medium",
            "category": "suspicious",
        },
    )

    detection = YaraAdapter()._detection_from_match(fake_match)

    assert detection.rule_id == "scanbox_test_rule"
    assert detection.category == "suspicious"
    assert detection.evidence["meta"]["title"] == "Test rule"
