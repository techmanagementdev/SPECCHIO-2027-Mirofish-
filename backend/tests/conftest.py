import os
import tempfile

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="specchio-test-")
for k in ["ACCESS_PASSWORD", "ADMIN_PASSWORD", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "LLM_PROVIDER"]:
    os.environ.pop(k, None)
