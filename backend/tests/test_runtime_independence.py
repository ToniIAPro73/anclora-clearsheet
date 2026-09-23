import os
import subprocess
import sys
from pathlib import Path

from server import app


def test_cors_uses_explicit_origins_with_credentials():
    cors = next(
        middleware
        for middleware in app.user_middleware
        if middleware.cls.__name__ == "CORSMiddleware"
    )
    assert cors.kwargs["allow_credentials"] is True
    assert "*" not in cors.kwargs["allow_origins"]
    assert cors.kwargs.get("allow_origin_regex") is None


def test_production_requires_jwt_secret():
    backend_dir = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.pop("JWT_SECRET", None)
    env["APP_ENV"] = "production"
    result = subprocess.run(
        [sys.executable, "-c", "import auth"],
        cwd=backend_dir,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "JWT_SECRET is required" in result.stderr
