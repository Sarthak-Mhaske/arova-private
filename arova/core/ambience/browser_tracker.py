import os
import glob
import sqlite3
import shutil
import tempfile
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class BrowserTabCapture:
    """
    Cross-platform browser tab & recent history scanner (Linux, macOS, Windows).
    Scans Chrome, Brave, Chromium, Firefox, and Edge session & history databases
    to extract authentic visited URLs and page titles.
    """
    @staticmethod
    def _is_noise_url(url: str, title: str) -> bool:
        url_lower = url.lower()
        title_lower = title.lower()

        # Social media noise
        if any(domain in url_lower for domain in ["instagram.com", "facebook.com", "tiktok.com", "twitter.com", "x.com"]):
            return True

        # Search engine query bloat & CAPTCHA redirects
        if any(skip in url_lower for skip in [
            "google.com/search", "google.com/sorry", "google.com/accounts", "google.com/url",
            "bing.com/search", "duckduckgo.com/?q=", "accounts.google.com", "/servicelogin",
            "/setosid", "oauth", "authuser", "login", "signin", "logout", "sso"
        ]):
            return True

        # Pure raw IPs without port/app
        if url_lower.rstrip('/') in ["http://127.0.0.1", "http://localhost"]:
            return True

        return False

    @staticmethod
    def _clean_url(url: str) -> str:
        # Strip ugly tracking and search bloat query parameters
        import urllib.parse
        try:
            parsed = urllib.parse.urlparse(url)
            # Remove tracking params (gs_lcrp, google_abuse, sei, utm_*, etc.)
            qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=False)
            filtered_qs = {
                k: v for k, v in qs.items() 
                if not any(k.startswith(p) or k == p for p in ["gs_lcrp", "google_abuse", "sei", "sourceid", "oq", "sclient", "utm_source", "utm_medium", "utm_campaign", "pli", "authuser"])
            }
            new_query = urllib.parse.urlencode(filtered_qs, doseq=True)
            clean = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
            return clean.rstrip('?')
        except Exception:
            return url

    @staticmethod
    def _categorize_url(url: str, title: str) -> str:
        text = f"{url} {title}".lower()
        if any(k in text for k in ["youtube.com/watch", "youtu.be", "tutorial", "learn", "course", "docs", "documentation", "arxiv", "paper", "medium.com", "dev.to", "wikipedia"]):
            return "study"
        if any(k in text for k in ["github.com", "gitlab.com", "localhost", "stack overflow", "stackoverflow.com", "api", "dashboard", "jira", "confluence"]):
            return "development"
        return "general"

    @staticmethod
    def get_recent_browser_history(limit: int = 15) -> List[Dict[str, str]]:
        urls: List[Dict[str, str]] = []
        seen_urls = set()

        # Build cross-platform history file search globs
        search_paths = []
        home = os.path.expanduser("~")

        # Linux
        search_paths.extend(glob.glob(os.path.join(home, ".config", "*[cC]hrome*", "Default", "History")))
        search_paths.extend(glob.glob(os.path.join(home, ".config", "*[bB]rave*", "Default", "History")))
        search_paths.extend(glob.glob(os.path.join(home, ".config", "*[cC]hromium*", "Default", "History")))
        search_paths.extend(glob.glob(os.path.join(home, ".mozilla", "firefox", "*.default*", "places.sqlite")))

        # macOS
        search_paths.extend(glob.glob(os.path.join(home, "Library", "Application Support", "Google", "Chrome", "Default", "History")))
        search_paths.extend(glob.glob(os.path.join(home, "Library", "Application Support", "BraveSoftware", "Brave-Browser", "Default", "History")))

        # Windows
        appdata = os.environ.get("LOCALAPPDATA", "")
        if appdata:
            search_paths.extend(glob.glob(os.path.join(appdata, "Google", "Chrome", "User Data", "Default", "History")))
            search_paths.extend(glob.glob(os.path.join(appdata, "BraveSoftware", "Brave-Browser", "User Data", "Default", "History")))
            search_paths.extend(glob.glob(os.path.join(appdata, "Microsoft", "Edge", "User Data", "Default", "History")))

        for path in search_paths:
            if not os.path.exists(path):
                continue
            tmp_path = None
            try:
                tmp_fd, tmp_path = tempfile.mkstemp(suffix=".sqlite")
                os.close(tmp_fd)
                shutil.copy2(path, tmp_path)

                conn = sqlite3.connect(tmp_path)
                c = conn.cursor()

                if "places.sqlite" in path:
                    query = """
                    SELECT url, title FROM moz_places 
                    WHERE url LIKE 'http%' AND title IS NOT NULL AND title != ''
                    ORDER BY last_visit_date DESC LIMIT ?
                    """
                else:
                    query = """
                    SELECT url, title FROM urls 
                    WHERE url LIKE 'http%' AND title IS NOT NULL AND title != ''
                    ORDER BY last_visit_time DESC LIMIT ?
                    """

                c.execute(query, (limit * 4,))
                for u, t in c.fetchall():
                    raw_url = str(u).strip()
                    clean_title = str(t).strip() if t else raw_url

                    # Check noise filter
                    if BrowserTabCapture._is_noise_url(raw_url, clean_title):
                        continue

                    clean_url = BrowserTabCapture._clean_url(raw_url)
                    if clean_url not in seen_urls:
                        seen_urls.add(clean_url)
                        cat = BrowserTabCapture._categorize_url(clean_url, clean_title)
                        urls.append({
                            "url": clean_url,
                            "title": clean_title,
                            "category": cat
                        })

                    if len(urls) >= limit:
                        break
                conn.close()
            except Exception as e:
                logger.debug(f"BrowserTabCapture failed scanning {path}: {e}")
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

            if len(urls) >= limit:
                break

        return urls[:limit]
