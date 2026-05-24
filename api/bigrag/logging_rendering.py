from __future__ import annotations

from structlog.dev import Column, ConsoleRenderer, KeyValueColumnFormatter, LogLevelColumnFormatter

from bigrag.logging_redaction import log_field_value


def console_renderer() -> ConsoleRenderer:
    styles = ConsoleRenderer.get_default_column_styles(True, True)
    level_styles = ConsoleRenderer.get_default_level_styles(True)
    level_styles = {key: value + styles.bright for key, value in level_styles.items()}
    return ConsoleRenderer(
        sort_keys=False,
        columns=[
            Column(
                "timestamp",
                KeyValueColumnFormatter(
                    key_style=None,
                    value_style=styles.timestamp,
                    reset_style=styles.reset,
                    value_repr=str,
                    width=8,
                ),
            ),
            Column(
                "level",
                LogLevelColumnFormatter(level_styles, reset_style=styles.reset, width=0),
            ),
            Column(
                "logger",
                KeyValueColumnFormatter(
                    key_style=None,
                    value_style=styles.logger_name,
                    reset_style=styles.reset,
                    value_repr=str,
                    width=22,
                ),
            ),
            Column(
                "event",
                KeyValueColumnFormatter(
                    key_style=None,
                    value_style=styles.bright,
                    reset_style=styles.reset,
                    value_repr=log_field_value,
                    width=30,
                ),
            ),
            Column(
                "",
                KeyValueColumnFormatter(
                    key_style=styles.kv_key,
                    value_style=styles.kv_value,
                    reset_style=styles.reset,
                    value_repr=log_field_value,
                ),
            ),
        ],
    )
