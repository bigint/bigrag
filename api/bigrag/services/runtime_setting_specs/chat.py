from __future__ import annotations

from bigrag.services.runtime_setting_specs._spec import SettingSpec

CHAT_SPECS: tuple[SettingSpec, ...] = (
    SettingSpec(
        key="chat_provider",
        group="chat",
        label="Default chat provider",
        kind="select",
        default="openai",
        description="Default provider for chat answers.",
        options=("openai", "openai_compatible"),
    ),
    SettingSpec(
        key="chat_model",
        group="chat",
        label="Default chat model",
        kind="string",
        default="gpt-4.1",
        description="Default model for chat answers.",
    ),
    SettingSpec(
        key="chat_base_url",
        group="chat",
        label="Chat base URL",
        kind="string",
        default=None,
        description="Optional OpenAI-compatible chat API base URL.",
    ),
    SettingSpec(
        key="chat_temperature",
        group="chat",
        label="Chat temperature",
        kind="float",
        default=0.2,
        description="Default sampling temperature for chat completions.",
        min=0,
        max=2,
    ),
    SettingSpec(
        key="chat_max_context_chars",
        group="chat",
        label="Max context characters",
        kind="int",
        default=120000,
        description="Retrieved source characters included in model context.",
        min=1000,
        max=2000000,
    ),
)
