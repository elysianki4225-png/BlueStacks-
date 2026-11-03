from pathlib import Path

from bluestacks_manager.config_store import ConfigStore, instance_id_from_key


def test_parses_and_preserves_comments(tmp_path: Path):
    path = tmp_path / "bluestacks.conf"
    path.write_text(
        "# global\n"
        'bst.instance.Rvc64.display_name="BlueStacks 5"\n'
        'bst.instance.Rvc64.enable_root_access="0"\n'
        "# keep me\n"
        'bst.instance.Rvc64.status.adb_port="5555"\n',
        encoding="utf-8",
    )
    store = ConfigStore.load(path)
    assert store.instance_ids() == ["Rvc64"]
    assert store.instance_value("Rvc64", "display_name") == "BlueStacks 5"
    assert instance_id_from_key("bst.instance.Rvc64.enable_root_access") == "Rvc64"
    store.set_instance_values("Rvc64", {"enable_root_access": "1"})
    store.save()
    reloaded = ConfigStore.load(path)
    assert reloaded.instance_value("Rvc64", "enable_root_access") == "1"
    assert "# keep me" in path.read_text(encoding="utf-8")


def test_new_instance_key_is_added_near_instance_section(tmp_path: Path):
    path = tmp_path / "bluestacks.conf"
    path.write_text(
        '# header\n'
        'bst.instance.Rvc64.display_name="One"\n'
        'bst.other="value"\n',
        encoding="utf-8",
    )
    store = ConfigStore.load(path)
    store.add_instance_id("Pie64_1")
    store.save()
    reloaded = ConfigStore.load(path)
    assert reloaded.instance_value("Pie64_1", "display_name") == "Pie64_1"
    assert reloaded.instance_value("Rvc64", "display_name") == "One"
