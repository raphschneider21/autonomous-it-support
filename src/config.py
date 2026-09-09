"""Loads `.env` once, before anything reads the environment.

`python-dotenv` has been in requirements.txt since the first commit but nothing
ever called it, so a key sitting in `.env` was simply ignored and every agent
quietly took its fallback path. Importing this module is what makes the file
take effect.

Real environment variables win over `.env` (`override=False`), so a value
exported in the shell — `EXECUTOR=real` on the VM, say — beats the file without
anyone having to edit it.
"""
import os

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency is in requirements.txt
    load_dotenv = None

_loaded = False


def load() -> bool:
    """Load `.env` from the project root. Idempotent; safe to call anywhere."""
    global _loaded
    if _loaded or load_dotenv is None:
        return _loaded

    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    load_dotenv(env_path, override=False)
    _loaded = True
    return True


def key_status() -> dict:
    """Whether a Claude key is configured — never the key itself."""
    load()
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    return {
        "configured": bool(key),
        "looks_valid": key.startswith("sk-ant-") and len(key) > 20,
        "length": len(key),
    }


load()
