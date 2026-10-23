import os

import pytest

# Tests never read the developer's real .env, never export to Langfuse and never see real keys.
os.environ["KB_ENV_FILE"] = os.path.join(os.path.dirname(__file__), "__no_env_file__")
for _key in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST", "OPENCODE_API_KEY", "KB_BUDGET_USD",
             "OPENCODE_BASE_URL", "LLM_MODEL", "PRICE_INPUT_PER_M", "PRICE_OUTPUT_PER_M", "MONGODB_URI",
             "KB_LLM_MODE", "KB_PAGE_CARDS", "KB_RERANKER", "KB_DATA_DIR"):
    os.environ.pop(_key, None)

from kb.config import get_settings  # noqa: E402


@pytest.fixture
def settings(tmp_path):
    return get_settings(data_dir=tmp_path / "data", opencode_api_key="test", llm_concurrency=4)
