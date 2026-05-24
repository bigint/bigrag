from __future__ import annotations

from dataclasses import dataclass

from bigrag.services.runtime_settings import get_values


@dataclass(frozen=True)
class ConversionSettings:
    timeout: int
    pdf_ocr_enabled: bool


async def load_conversion_settings() -> ConversionSettings:
    runtime = await get_values(["conversion_timeout", "conversion_pdf_ocr_enabled"])
    return ConversionSettings(
        timeout=runtime["conversion_timeout"],
        pdf_ocr_enabled=runtime["conversion_pdf_ocr_enabled"],
    )
