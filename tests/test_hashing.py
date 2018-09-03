from electron.hashing import hex_digest


def test_hex_digest():
    some_string = "something"
    assert isinstance(hex_digest(some_string), str)
