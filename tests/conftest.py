import pytest

from kb.config import get_settings


@pytest.fixture
def settings(tmp_path):
    return get_settings(data_dir=tmp_path / "data", opencode_api_key="test", llm_concurrency=4)
