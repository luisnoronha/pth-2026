"""The one factory that builds Rex, used by the CLI and the Rex Lambda."""

from strands import Agent
from strands.hooks import HookProvider
from strands.models.model import Model

from leash.common.config import model_settings
from leash.hooks.levels import hooks_for
from leash.rex.briefing import Briefing
from leash.rex.prompts import SYSTEM_PROMPT
from leash.rex.tools import TOOLS


def build_model() -> Model:
    """The model chosen in strands/rex.yaml (or overridden by env / --model).

    Same Rex, same tools, same hooks: only the brain changes. API keys come from
    the environment (ANTHROPIC_API_KEY / OPENAI_API_KEY), never from the repo.
    """
    s = model_settings()
    params = {**s.params, **({} if s.temperature is None else {"temperature": s.temperature})}
    if s.provider == "anthropic":
        from strands.models.anthropic import AnthropicModel

        return AnthropicModel(model_id=s.model_id, max_tokens=s.max_tokens, params=params)
    from strands.models.openai import OpenAIModel

    return OpenAIModel(model_id=s.model_id, params={"max_completion_tokens": s.max_tokens, **params})


def build_rex(level: int, model: Model | None = None, extra_hooks: list[HookProvider] | None = None) -> Agent:
    """Rex at a given leash level. `extra_hooks` is for things like console output."""
    return Agent(
        name="Rex",
        model=model or build_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=list(TOOLS),
        structured_output_model=Briefing,
        hooks=[*hooks_for(level), *(extra_hooks or [])],
        callback_handler=None,
    )
