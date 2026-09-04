import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI

load_dotenv()

# ==========================================================
# LLM provider abstraction.
#
# The RAG agents only ever talk to this factory. Provider
# selection is infrastructure/configuration, never logic.
#
# Default strategy: PRIMARY provider first, then FALLBACK.
#
#   PRIMARY_LLM_PROVIDER=groq
#   FALLBACK_LLM_PROVIDER=openrouter
#
# Env configuration:
#
#   GROQ_API_KEY                (required for groq)
#   GROQ_MODEL                  openai/gpt-oss-20b
#
#   OPENROUTER_API_KEY          (required for openrouter)
#   OPENROUTER_MODEL            minimax/minimax-m3:free
#   OPENROUTER_BASE_URL         https://openrouter.ai/api/v1
#
#   LLM_PROVIDER=lmstudio       optional manual override to a
#   LM_STUDIO_BASE_URL          http://localhost:1234/v1
#   LM_STUDIO_MODEL             qwen/qwen3-8b
#
# create_llm() with no arguments returns a FailoverLLM that
# tries the primary provider and falls back to the secondary
# when the first raises (e.g. HTTP 429 rate limiting). Only
# when every configured provider fails does the caller see an
# error -> the agents return a structured "All LLM providers
# unavailable" result instead of a guessed answer.
# ==========================================================

DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"

DEFAULT_OPENROUTER_MODEL = "minimax/minimax-m3:free"

DEFAULT_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

DEFAULT_LM_STUDIO_BASE_URL = "http://localhost:1234/v1"

DEFAULT_LM_STUDIO_MODEL = "qwen/qwen3-8b"


class ProviderUnavailableError(RuntimeError):
    """
    Raised when every configured LLM provider failed.

    `reason` is a human-readable explanation meant to surface
    as the agent's structured error reason, and `cause` holds
    the last underlying provider exception.
    """

    def __init__(self, reason, cause=None):
        super().__init__(reason)
        self.reason = reason
        self.cause = cause


class FailoverLLM:
    """
    Tries each provider in order; the first successful response
    wins. Providers are tried strictly in sequence, so a slow
    primary never starves the fallback after a failure has
    already been raised.

    If every provider fails, raises ProviderUnavailableError.
    """

    def __init__(self, providers):
        self.providers = list(providers)

    def invoke(self, prompt, **kwargs):

        last_error = None

        for provider in self.providers:

            try:
                return provider.invoke(prompt, **kwargs)

            except Exception as exc:  # noqa: BLE001
                last_error = exc
                continue

        raise ProviderUnavailableError(
            "All LLM providers unavailable",
            cause=last_error,
        )


def _require_env(name):
    value = os.getenv(name)

    if value is None or not value.strip():
        raise ValueError(
            f"Missing {name} for the selected LLM provider."
        )

    return value.strip()


def _build_groq():

    return ChatGroq(
        model=os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL),
        api_key=_require_env("GROQ_API_KEY"),
        temperature=0,
    )


def _build_openrouter():

    return ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL),
        api_key=_require_env("OPENROUTER_API_KEY"),
        base_url=os.getenv(
            "OPENROUTER_BASE_URL",
            DEFAULT_OPENROUTER_BASE_URL,
        ),
        temperature=0,
    )


def _build_lmstudio():

    return ChatOpenAI(
        model=os.getenv("LM_STUDIO_MODEL", DEFAULT_LM_STUDIO_MODEL),
        base_url=os.getenv(
            "LM_STUDIO_BASE_URL",
            DEFAULT_LM_STUDIO_BASE_URL,
        ),
        api_key=os.getenv("LM_STUDIO_API_KEY", "not-needed"),
        temperature=0,
    )


def _provider_chain(prefer=None):
    """
    Build the list of provider LLMs from PRIMARY_LLM_PROVIDER
    and FALLBACK_LLM_PROVIDER (defaults: groq then openrouter).

    `prefer` is an optional stage tag ("answer" or "grounding")
    that lets a specific agent stage override the provider order
    through dedicated env vars, e.g.:

        ANSWER_LLM_PROVIDER=openrouter
        ANSWER_LLM_FALLBACK_PROVIDER=groq

    This keeps provider selection configuration-driven rather
    than baked into agent logic.

    Providers whose API key is missing are skipped so the rest
    of the chain still works.
    """

    if prefer:

        primary = os.getenv(
            f"{prefer.upper()}_LLM_PROVIDER",
            os.getenv("PRIMARY_LLM_PROVIDER", "groq"),
        ).strip().lower()

        fallback = os.getenv(
            f"{prefer.upper()}_LLM_FALLBACK_PROVIDER",
            os.getenv("FALLBACK_LLM_PROVIDER", "openrouter"),
        ).strip().lower()

    else:

        primary = os.getenv(
            "PRIMARY_LLM_PROVIDER",
            "groq",
        ).strip().lower()

        fallback = os.getenv(
            "FALLBACK_LLM_PROVIDER",
            "openrouter",
        ).strip().lower()

    names = []

    for name in (primary, fallback):
        if name and name not in names:
            names.append(name)

    chain = []

    for name in names:

        try:

            if name == "groq":
                chain.append(_build_groq())

            elif name == "openrouter":
                chain.append(_build_openrouter())

            elif name == "lmstudio":
                chain.append(_build_lmstudio())

        except ValueError:
            # Missing API key for that provider -> skip it
            # instead of breaking the whole chain.
            continue

    return chain


def create_llm(provider=None, prefer=None):
    """
    Create an LLM object.

    Explicit `provider` (or the LLM_PROVIDER env override) may
    be "groq", "openrouter" or "lmstudio" to force a single
    provider.

    `prefer` is an optional stage tag ("answer" or "grounding")
    that re-orders the provider chain via purpose-specific env
    vars (e.g. ANSWER_LLM_PROVIDER / ANSWER_LLM_FALLBACK_PROVIDER),
    falling back to the global primary/fallback otherwise. Used by
    the answer-generation and grounding agents to prefer the
    stronger OpenRouter model without changing the other agents.

    With no override, returns a FailoverLLM over the configured
    primary/fallback providers.
    """

    override = provider

    if override is None:
        override = os.getenv("LLM_PROVIDER")

    if override:

        override = override.strip().lower()

        if override == "groq":
            return _build_groq()

        if override == "openrouter":
            return _build_openrouter()

        if override == "lmstudio":
            return _build_lmstudio()

    chain = _provider_chain(prefer=prefer)

    if not chain:
        raise ValueError(
            "No LLM provider available. Add GROQ_API_KEY and/or "
            "OPENROUTER_API_KEY to the .env file."
        )

    return FailoverLLM(chain)