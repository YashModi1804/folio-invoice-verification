import json

from scripts import export_public_preview


def test_public_preview_uses_only_synthetic_domain_fixtures(tmp_path, monkeypatch):
    monkeypatch.setattr(export_public_preview, "DESTINATION", tmp_path)
    export_public_preview.export()

    examples = json.loads((tmp_path / "data.json").read_text(encoding="utf-8"))
    assert [example["kind"] for example in examples] == ["clean", "variance", "uncertain"]
    assert [example["job"]["status"] for example in examples] == [
        "AUTO_APPROVED",
        "REQUIRES_HUMAN_REVIEW",
        "REQUIRES_HUMAN_REVIEW",
    ]
    assert examples[1]["job"]["result"]["checks"][-1]["variance"] == "50.00"
    assert all(example["job"]["mode"] == "fixture" for example in examples)
    telemetry = [example["job"]["result"]["telemetry"] for example in examples]
    assert all(item["input_tokens"] is None for item in telemetry)
    assert len(list(tmp_path.glob("*.png"))) == 6
