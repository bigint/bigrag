from __future__ import annotations

import asyncio
import logging
from urllib.parse import urljoin, urlparse

import httpx

logger = logging.getLogger("bigrag.crawler")

_CRAWL_TIMEOUT = 30
_MAX_CONTENT_SIZE = 50 * 1024 * 1024  # 50MB per page


async def fetch_url(url: str) -> tuple[str, bytes]:
    """Fetch a single URL. Returns (final_url, content_bytes)."""
    async with httpx.AsyncClient(
        timeout=_CRAWL_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": "bigrag-crawler/1.0"},
    ) as client:
        response = await client.get(url)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if not any(
            t in content_type
            for t in (
                "text/html",
                "text/plain",
                "application/xhtml",
                "text/xml",
                "application/xml",
                "text/markdown",
            )
        ):
            raise ValueError(f"Unsupported content type: {content_type}")

        if len(response.content) > _MAX_CONTENT_SIZE:
            raise ValueError(f"Content too large: {len(response.content)} bytes")

        return str(response.url), response.content


def _extract_links(html: str, base_url: str) -> list[str]:
    """Extract absolute HTTP(S) links from HTML content."""
    import re

    links = set()
    for match in re.finditer(r'href=["\']([^"\']+)["\']', html):
        href = match.group(1)
        if href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme in ("http", "https"):
            # Strip fragment
            clean = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            if parsed.query:
                clean += f"?{parsed.query}"
            links.add(clean)
    return list(links)


async def crawl(
    url: str,
    max_depth: int = 0,
    max_pages: int = 1,
    same_domain_only: bool = True,
) -> list[dict]:
    """Crawl a URL and optionally follow links.

    Returns list of {"url": str, "content": bytes}
    """
    visited: set[str] = set()
    results: list[dict] = []
    base_domain = urlparse(url).netloc

    async def _crawl_page(page_url: str, depth: int) -> None:
        if page_url in visited or len(results) >= max_pages:
            return
        visited.add(page_url)

        try:
            final_url, content = await fetch_url(page_url)
            results.append({
                "url": final_url,
                "content": content,
            })
            logger.info(f"Crawled: {final_url} ({len(content)} bytes)")

            if depth < max_depth and len(results) < max_pages:
                try:
                    html = content.decode("utf-8", errors="replace")
                except Exception:
                    return
                links = _extract_links(html, final_url)

                for link in links:
                    if len(results) >= max_pages:
                        break
                    if same_domain_only and urlparse(link).netloc != base_domain:
                        continue
                    if link not in visited:
                        await _crawl_page(link, depth + 1)

        except Exception as e:
            logger.warning(f"Failed to crawl {page_url}: {e}")

    await _crawl_page(url, 0)
    return results
