"""Which chat models the Assistant can use right now, for its model picker.

- On this computer: the models downloaded in Settings → AI (and the runtime).
- OpenAI-compatible (Ollama, LM Studio, a cloud service): what the server lists
  at /models.
- Claude: a few current models.
"""

import json
import urllib.request

from aurora import settings

ANTHROPIC = ("claude-sonnet-5", "claude-opus-5", "claude-haiku-4-5")
KEYS = {"local": "ai-model", "openai": "ai-openai-model", "anthropic": "ai-anthropic-model"}


def local_models():
    """[(id, name)] of downloaded chat models, if the runtime is installed too."""
    from aurora.ai import catalog, components
    if not components.runtime_installed():
        return []
    return [(model_id, item.get("name", model_id)) for model_id, item in catalog()["chat"].items()
            if components.model_installed("chat", model_id)]


def parse_model_list(data):
    """Model ids from an OpenAI-style /models answer (Ollama and LM Studio too),
    leaving out embedding and speech models, which can't chat."""
    items = data.get("data", []) if isinstance(data, dict) else []
    ids = [m.get("id") for m in items if isinstance(m, dict) and isinstance(m.get("id"), str)]
    skip = ("embed", "whisper", "tts", "dall-e", "moderation")
    return sorted(i for i in ids if not any(word in i.lower() for word in skip))


def openai_models(base, api_key="", timeout=4):
    """Model ids the server offers; raises OSError when it can't be reached."""
    request = urllib.request.Request(base.rstrip("/") + "/models")
    if api_key:
        request.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return parse_model_list(json.load(response))
    except ValueError as err:
        raise OSError(f"unexpected answer from {base}") from err


def available():
    """(provider, [(id, label)], current id). Raises OSError for a server that
    doesn't answer."""
    from aurora.ai import keys, provider
    which = provider()
    s = settings.get()
    current = s.get_string(KEYS.get(which, "ai-model")) if s else ""
    if which == "local":
        models = local_models()
    elif which == "openai":
        base = s.get_string("ai-openai-url") if s else ""
        models = [(m, m) for m in openai_models(base, keys.get("openai") or "")]
    else:
        models = [(m, m) for m in ANTHROPIC]
        if current and current not in ANTHROPIC:
            models.insert(0, (current, current))
    return which, models, current


def choose(which, model_id):
    s = settings.get()
    if s is not None and which in KEYS:
        s.set_string(KEYS[which], model_id)
