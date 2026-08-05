from council.storage.optimizer import audit, optimize, setup_persist_structure, what_if_delete


def test_audit_keys():
    data = audit()
    assert "agents" in data
    assert "total_keep" in data


def test_what_if_shape():
    data = what_if_delete()
    assert "files" in data
    assert "total_size" in data


def test_setup_ok():
    data = setup_persist_structure()
    assert data["ok"] is True


def test_optimize_dry_run():
    data = optimize(dry_run=True)
    assert data["dry_run"] is True
    assert "actions" in data
