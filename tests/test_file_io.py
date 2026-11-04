import json

import file_io


def test_transient_windows_replace_lock_keeps_previous_receipt_valid(
    tmp_path, monkeypatch
):
    path = tmp_path / "receipt.json"
    path.write_text('{"status":"previous"}')
    original = file_io.os.replace
    calls = []

    def replace(source, destination):
        calls.append(1)
        if len(calls) < 3:
            assert json.loads(path.read_text())["status"] == "previous"
            raise PermissionError("Transient Windows file lock")
        original(source, destination)

    monkeypatch.setattr(file_io.os, "replace", replace)
    file_io.atomic_json(path, {"status": "complete"})
    assert len(calls) == 3
    assert json.loads(path.read_text()) == {"status": "complete"}
