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
import socket

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


def _enabled(name: str, default: str = "0") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


def demo_mode_enabled() -> bool:
    """Whether the intentionally deterministic graded-demo profile is active."""
    load()
    return _enabled("DEMO_MODE")


def agent_mode() -> str:
    """Return ``deterministic`` or ``live``/``auto`` for runtime selection.

    The launcher sets this explicitly.  Keeping ``auto`` as the non-demo
    default preserves the repository's optional model-backed development path.
    """
    load()
    configured = os.environ.get("AGENT_MODE", "").strip().lower()
    # DEMO_MODE is a safety boundary. Preflight still reports a conflicting
    # requested value, but the runtime itself degrades safely to deterministic.
    if demo_mode_enabled():
        return "deterministic"
    if configured in ("deterministic", "fallback", "mock", "offline"):
        return "deterministic"
    if configured in ("live", "model", "auto"):
        return configured
    return "auto"


def requested_agent_mode() -> str:
    """Raw configured agent mode, exposed so configuration conflicts are clear."""
    load()
    return os.environ.get("AGENT_MODE", "auto").strip().lower() or "auto"


def external_model_enabled() -> bool:
    """True only when the configured agent path may call an external model."""
    return agent_mode() != "deterministic"


def endpoint_name() -> str:
    """Stable endpoint identity used by health and demo reporting."""
    load()
    if demo_mode_enabled():
        from .demo.state import ENDPOINT_NAME
        return ENDPOINT_NAME
    return (
        os.environ.get("ENDPOINT_NAME")
        or os.environ.get("ENDPOINT_HOSTNAME")
        or socket.gethostname()
    )


load()
