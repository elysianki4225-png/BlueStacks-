from pathlib import Path

from bluestacks_manager.backend import ManagerBackend


def make_config(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                'bst.instance.Rvc64.display_name="BlueStacks 5"',
                'bst.instance.Rvc64.enable_root_access="0"',
                'bst.instance.Rvc64.device_profile_code="sttu"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def test_backend_operations(tmp_path: Path):
    config = tmp_path / "bluestacks.conf"
    make_config(config)
    backend = ManagerBackend(config_path=str(config), token="test-token")
    assert backend.authenticate("test-token")
    assert not backend.authenticate("wrong")
    instances = backend.instances()
    assert instances[0]["instance_id"] == "Rvc64"
    root = backend.set_root(["Rvc64"], True)
    assert root["changed"]
    device = backend.set_device(["Rvc64"], {"model": "Galaxy S23", "brand": "Samsung", "manufacturer": "samsung"})
    assert device["changed"]
    backups = backend.backups()
    assert len(backups) == 2
    state = backend.state()
    assert state["app_name"] == "蓝叠国际版管理器"
