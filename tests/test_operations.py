from pathlib import Path

from bluestacks_manager.backup import list_backups
from bluestacks_manager.config_store import ConfigStore
from bluestacks_manager.operations import set_device, set_root


def write_config(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                'bst.instance.Rvc64.display_name="BlueStacks 5"',
                'bst.instance.Rvc64.enable_root_access="0"',
                'bst.instance.Rvc64.device_profile_code="sttu"',
                'bst.instance.Pie64_1.display_name="BlueStacks 1"',
                'bst.instance.Pie64_1.enable_root_access="1"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_set_root_and_device_creates_backup(tmp_path: Path):
    config = tmp_path / "bluestacks.conf"
    write_config(config)
    root_result = set_root(config, ["Rvc64"], True)
    assert root_result.changed
    assert root_result.backup is not None
    store = ConfigStore.load(config)
    assert store.instance_value("Rvc64", "enable_root_access") == "1"
    assert len(list_backups(config)) == 1

    device_result = set_device(
        config,
        ["Pie64_1"],
        {
            "profile_code": "snpe",
            "manufacturer": "samsung",
            "brand": "Samsung",
            "model": "Galaxy S8",
            "width": 1440,
            "height": 2960,
            "dpi": 240,
        },
    )
    assert device_result.changed
    store = ConfigStore.load(config)
    assert store.instance_value("Pie64_1", "device_custom_model") == "Galaxy S8"
    assert store.instance_value("Pie64_1", "fb_height") == "2960"
