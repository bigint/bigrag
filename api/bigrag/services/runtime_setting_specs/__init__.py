from __future__ import annotations

from bigrag.services.runtime_setting_specs._spec import SettingSource, SettingSpec
from bigrag.services.runtime_setting_specs.backups import BACKUPS_SPECS
from bigrag.services.runtime_setting_specs.chat import CHAT_SPECS
from bigrag.services.runtime_setting_specs.ingestion import INGESTION_SPECS
from bigrag.services.runtime_setting_specs.queue import QUEUE_SPECS
from bigrag.services.runtime_setting_specs.retention import RETENTION_SPECS
from bigrag.services.runtime_setting_specs.search import SEARCH_SPECS
from bigrag.services.runtime_setting_specs.security import SECURITY_SPECS
from bigrag.services.runtime_setting_specs.vector_store import VECTOR_STORE_SPECS
from bigrag.services.runtime_setting_specs.webhooks import WEBHOOKS_SPECS

SETTING_SPECS: tuple[SettingSpec, ...] = (
    *SECURITY_SPECS,
    *INGESTION_SPECS,
    *QUEUE_SPECS,
    *BACKUPS_SPECS,
    *VECTOR_STORE_SPECS,
    *SEARCH_SPECS,
    *CHAT_SPECS,
    *WEBHOOKS_SPECS,
    *RETENTION_SPECS,
)

REGISTRY = {spec.key: spec for spec in SETTING_SPECS}

__all__ = [
    "REGISTRY",
    "SETTING_SPECS",
    "SettingSource",
    "SettingSpec",
]
