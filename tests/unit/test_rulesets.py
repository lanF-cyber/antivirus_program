from pathlib import Path

from scanbox.core.rulesets import CAPA_RULE_EXTENSIONS, inspect_ruleset


def test_inspect_ruleset_counts_only_capa_rule_files(tmp_path: Path) -> None:
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "alpha.yml").write_text("rule: alpha", encoding="utf-8")
    (rules_dir / "beta.yaml").write_text("rule: beta", encoding="utf-8")
    (rules_dir / "README.md").write_text("docs", encoding="utf-8")
    (rules_dir / ".hidden.yml").write_text("hidden", encoding="utf-8")
    hidden_dir = rules_dir / ".github" / "workflows"
    hidden_dir.mkdir(parents=True)
    (hidden_dir / "release.yml").write_text("name: release", encoding="utf-8")

    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        '{"name":"official-capa-rules","version":"v9.3.0","source":"https://github.com/mandiant/capa-rules","pinned_ref":"v9.3.0","vendor_status":"vendored","vendored_at":"2026-04-14T00:00:00Z","rule_count":2}',
        encoding="utf-8",
    )

    inspection = inspect_ruleset(
        engine="capa",
        rules_dir=rules_dir,
        manifest_path=manifest,
        rule_extensions=CAPA_RULE_EXTENSIONS,
        require_vendor_status=True,
    )

    assert inspection.rule_count == 2
    assert inspection.has_mismatch is False


def test_inspect_ruleset_detects_placeholder_with_zero_rules(tmp_path: Path) -> None:
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "README.md").write_text("placeholder", encoding="utf-8")

    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        '{"name":"official-capa-rules","version":"v9.3.0","source":"https://github.com/mandiant/capa-rules","pinned_ref":"v9.3.0","vendor_status":"placeholder","vendored_at":null,"rule_count":0}',
        encoding="utf-8",
    )

    inspection = inspect_ruleset(
        engine="capa",
        rules_dir=rules_dir,
        manifest_path=manifest,
        rule_extensions=CAPA_RULE_EXTENSIONS,
        require_vendor_status=True,
    )

    assert inspection.placeholder is True
    assert inspection.rule_count == 0
    assert inspection.has_mismatch is False
