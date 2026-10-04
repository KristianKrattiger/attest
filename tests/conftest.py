import json

import pytest


@pytest.fixture
def write_json(tmp_path):
    """write_json(name, data) -> path of a JSON file written into tmp_path."""
    def write(name, data):
        path = tmp_path / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path
    return write
