from bluestacks_manager.random_device import generate_device


def test_generate_device_has_all_fields():
    device = generate_device()
    assert set(device) == {
        "profile_code",
        "manufacturer",
        "brand",
        "model",
        "width",
        "height",
        "dpi",
    }
    assert device["manufacturer"]
    assert device["brand"]
    assert device["model"]
    assert device["width"] > 0
    assert device["height"] > 0
    assert device["dpi"] > 0


def test_generate_device_allows_overrides():
    device = generate_device(manufacturer="samsung", brand="Samsung", model="Galaxy S8", profile_code="snpe")
    assert device["manufacturer"] == "samsung"
    assert device["brand"] == "Samsung"
    assert device["model"] == "Galaxy S8"
    assert device["profile_code"] == "snpe"
