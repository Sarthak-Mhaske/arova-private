import re
import urllib.parse
import urllib.request
import logging
import asyncio
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"

def strip_emojis(text: str) -> str:
    """
    Strictly removes all emojis and Unicode pictographs from text.
    """
    if not text:
        return ""
    # Unicode ranges for emojis, pictographs, symbols
    emoji_pattern = re.compile(
        "[\U00010000-\U0010ffff"  # Supplementary Multilingual Plane (modern emojis)
        "\u2600-\u27bf"           # Miscellaneous Symbols & Dingbats
        "\u2300-\u23ff"           # Miscellaneous Technical
        "\u2b50-\u2b55"           # Stars and geometric symbols
        "\u200d"                  # Zero-width joiner
        "\ufe0f"                  # Variation Selector-16
        "]+",
        flags=re.UNICODE
    )
    # Clean emojis and normalize whitespace
    cleaned = emoji_pattern.sub("", text)
    cleaned = re.sub(r' +', ' ', cleaned)
    return cleaned.strip()


def live_web_search_sync(query: str, max_results: int = 6) -> Dict[str, Any]:
    """
    Performs synchronous live web search using DuckDuckGo Lite endpoint without requiring third-party API keys.
    Returns structured results list containing titles, snippets, and URLs.
    """
    if not query:
        return {"query": query, "results": [], "error": "Empty query"}

    url = "https://lite.duckduckgo.com/lite/"
    post_data = urllib.parse.urlencode({"q": query}).encode("utf-8")
    
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://lite.duckduckgo.com/"
    }

    try:
        req = urllib.request.Request(url, data=post_data, headers=headers)
        with urllib.request.urlopen(req, timeout=8.0) as response:
            html = response.read().decode("utf-8", errors="replace")

        # Parse links and snippets
        raw_links = re.findall(r'<a\s+[^>]*href=[\'"]([^\'"]+)[\'"][^>]*class=[\'"]result-link[\'"][^>]*>(.*?)</a>', html, re.DOTALL)
        if not raw_links:
            raw_links = re.findall(r'<a\s+[^>]*class=[\'"]result-link[\'"][^>]*href=[\'"]([^\'"]+)[\'"][^>]*>(.*?)</a>', html, re.DOTALL)
            
        raw_snippets = re.findall(r'<td\s+[^>]*class=[\'"]result-snippet[\'"][^>]*>(.*?)</td>', html, re.DOTALL)

        results: List[Dict[str, str]] = []
        for idx in range(min(max_results, len(raw_links))):
            link_url, title_html = raw_links[idx]
            title = re.sub(r'<[^>]+>', '', title_html).replace('&amp;', '&').replace('&quot;', '"').strip()
            
            snippet = ""
            if idx < len(raw_snippets):
                snippet = re.sub(r'<[^>]+>', '', raw_snippets[idx]).replace('&amp;', '&').replace('&quot;', '"').strip()

            # Resolve DuckDuckGo redirect URL
            actual_url = link_url
            if "uddg=" in link_url:
                m = re.search(r'uddg=([^&]+)', link_url)
                if m:
                    actual_url = urllib.parse.unquote(m.group(1))

            if title or snippet:
                results.append({
                    "title": strip_emojis(title),
                    "snippet": strip_emojis(snippet),
                    "url": actual_url
                })

        # Format clean text block for cognitive synthesis
        text_lines = [f"[LIVE WEB SEARCH RESULTS FOR: '{query}']"]
        for idx, res in enumerate(results, 1):
            text_lines.append(f"{idx}. {res['title']}")
            if res['snippet']:
                text_lines.append(f"   Summary: {res['snippet']}")
            if res['url']:
                text_lines.append(f"   Source: {res['url']}")
            text_lines.append("")

        text_block = "\n".join(text_lines).strip()
        logger.info(f"Live web search for '{query}' retrieved {len(results)} results.")
        return {
            "query": query,
            "results": results,
            "text_block": text_block,
            "count": len(results)
        }
    except Exception as e:
        logger.warning(f"Live web search failed for '{query}': {e}")
        return {
            "query": query,
            "results": [],
            "text_block": f"[Web search for '{query}' returned no external hits ({e})]",
            "error": str(e)
        }


async def live_web_search(query: str, max_results: int = 6) -> Dict[str, Any]:
    """
    Asynchronous wrapper for live web search.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, live_web_search_sync, query, max_results)
