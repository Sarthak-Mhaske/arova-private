import os
import time
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
    # Dangerous / Sensitive categories and noise that should NEVER be captured or restored
    CRITICAL_PRIVACY_PATTERNS = [
        # 1. Banking, Payments, and Crypto/Trading
        "bank", "paypal.com", "stripe.com", "razorpay.com", "chase.com", "wellsfargo.com",
        "zerodha.com", "groww.in", "hdfcbank.com", "icicibank.com", "sbi.co.in", "checkout", "billing", "payment",
        # 2. Authentication, Credential Resets, Identity Providers & SSO
        "password", "reset_password", "two-factor", "2fa", "accounts.google.com", "login.microsoftonline.com",
        "login.live.com", "auth0.com", "okta.com", "idp.", "/oauth2/", "/setosid", "/servicelogin",
        "token=", "session_token=", "signin", "signup", "saml", "login.windows.net", "appleid.apple.com",
        # 3. Sensitive Personal (Health, Tax, Legal, Govt IDs)
        "tax", "irs.gov", "incometax", "aadhaar", "passport", "health", "medical",
        # 4. Search Engine Noise, Captchas, and Bot Protection
        "google.com/search", "google.com/sorry", "bing.com/search", "duckduckgo.com/?q=", "recaptcha", "cloudflare.com",
        # 5. Social Media Entertainment & Ephemeral Distractions
        "instagram.com", "tiktok.com", "facebook.com", "twitter.com", "x.com", "pinterest.com",
        "web.whatsapp.com", "messenger.com", "chat.google.com",
        # 6. Transient HTTP Error Pages & Not Found
        "page not found", "404 not found", "500 internal server error", "access denied", "bad gateway",
        "site can't be reached", "error 404", "403 forbidden", "github.com/404",
        # 7. Internal Arova and Local Dev Bridges
        "localhost:8765", "127.0.0.1:8765", "localhost:5173", "127.0.0.1:5173", "localhost:1420", "127.0.0.1:1420"
    ]

    @classmethod
    def _is_noise_url(cls, url: str, title: str) -> bool:
        url_lower = url.lower()
        title_lower = title.lower()

        # Strict Critical Privacy and Noise check
        if any(pat in url_lower or pat in title_lower for pat in cls.CRITICAL_PRIVACY_PATTERNS):
            return True

        # Pure raw IPs without port/app
        if url_lower.rstrip('/') in ["http://127.0.0.1", "http://localhost", "https://localhost"]:
            return True

        # Generic blank or browser default titles
        if title_lower in ["new tab", "home", "untitled", "about:blank", "loading...", "page not found"]:
            return True

        return False

    @staticmethod
    def _clean_url(url: str, title: str = "") -> tuple:
        """
        Strips tracking bloat, canonicalizes subdomains, cleans badge notifications,
        and groups commit/hash URLs into the parent repository context.
        Returns (clean_url, optional_sanitized_title).
        """
        import urllib.parse
        import re
        try:
            # Clean notification badges like '(3) ', '(12) ', '[5] ' from title
            clean_title = re.sub(r'^\s*[\(\[]\d+[\)\]]\s*', '', title).strip() if title else ""
            
            # Clean browser name suffixes from title
            for suffix in [" - Google Chrome", " - Brave", " - Mozilla Firefox", " - Microsoft Edge", " - Chromium", " - Arc"]:
                if clean_title.endswith(suffix):
                    clean_title = clean_title[:-len(suffix)].strip()

            parsed = urllib.parse.urlparse(url)
            netloc = parsed.netloc.lower()
            path = parsed.path.rstrip('/')

            # Canonicalize Padlet domains (padlet.app -> padlet.com)
            if netloc == "padlet.app":
                netloc = "padlet.com"

            # 1. Canonicalize GitHub commit/pull hash pages to main repo or clean PR/Issue title
            if "github.com" in netloc:
                parts = [p for p in path.split('/') if p]
                if len(parts) >= 4 and parts[2] in ["commit", "commits"]:
                    # Group commit pages under the repository
                    repo_url = f"https://github.com/{parts[0]}/{parts[1]}"
                    return repo_url, f"{parts[0]}/{parts[1]} · GitHub"
                elif len(parts) >= 4 and parts[2] in ["pull", "issues"]:
                    clean_path = f"/{parts[0]}/{parts[1]}/{parts[2]}/{parts[3]}"
                    return f"https://github.com{clean_path}", clean_title or f"GitHub #{parts[3]}"

            # 2. General URLs: strip tracking query parameters
            qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=False)
            filtered_qs = {
                k: v for k, v in qs.items() 
                if not any(k.startswith(p) or k == p for p in [
                    "gs_lcrp", "google_abuse", "sei", "sourceid", "oq", "sclient", 
                    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
                    "pli", "authuser", "ref", "fbclid", "gclid", "v", "_ga"
                ])
            }
            new_query = urllib.parse.urlencode(filtered_qs, doseq=True)
            clean = urllib.parse.urlunparse((parsed.scheme or "https", netloc, path, parsed.params, new_query, ""))
            return clean.rstrip('?'), (clean_title if clean_title != title else None)
        except Exception:
            return url, None

    @staticmethod
    def _categorize_url(url: str, title: str) -> str:
        text = f"{url} {title}".lower()
        if any(k in text for k in ["github.com", "gitlab.com", "localhost", "stack overflow", "stackoverflow.com", "api", "dashboard", "jira", "confluence", "linear.app", "notion.so"]):
            return "development"
        if any(k in text for k in ["youtube.com/watch", "youtu.be", "tutorial", "learn", "course", "docs", "documentation", "arxiv", "paper", "medium.com", "dev.to", "wikipedia", "arena.ai", "padlet"]):
            return "research"
        return "general"

    @staticmethod
    def get_recent_browser_history(limit: int = 10, max_age_hours: float = 12.0) -> List[Dict[str, str]]:
        """
        Extracts genuine browser tabs visited during the current/last active work session (default: last 12 hours).
        Converts browser-specific epoch timestamps and strictly filters out stale history.
        """
        urls: List[Dict[str, str]] = []
        seen_urls = set()
        seen_titles = set()
        now = time.time()

        # Chrome/Brave epoch: microseconds since Jan 1, 1601 UTC
        min_chrome_time = (now - max_age_hours * 3600 + 11644473600) * 1000000
        # Firefox epoch: microseconds since Jan 1, 1970 UTC
        min_firefox_time = (now - max_age_hours * 3600) * 1000000

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
        roaming = os.environ.get("APPDATA", "")
        if appdata:
            search_paths.extend(glob.glob(os.path.join(appdata, "Google", "Chrome", "User Data", "*", "History")))
            search_paths.extend(glob.glob(os.path.join(appdata, "BraveSoftware", "Brave-Browser", "User Data", "*", "History")))
            search_paths.extend(glob.glob(os.path.join(appdata, "Microsoft", "Edge", "User Data", "*", "History")))
            search_paths.extend(glob.glob(os.path.join(appdata, "Arc", "User Data", "*", "History")))
        if roaming:
            search_paths.extend(glob.glob(os.path.join(roaming, "Mozilla", "Firefox", "Profiles", "*", "places.sqlite")))

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
                    AND last_visit_date >= ?
                    ORDER BY last_visit_date DESC LIMIT ?
                    """
                    c.execute(query, (min_firefox_time, limit * 2))
                else:
                    query = """
                    SELECT url, title FROM urls 
                    WHERE url LIKE 'http%' AND title IS NOT NULL AND title != ''
                    AND last_visit_time >= ?
                    ORDER BY last_visit_time DESC LIMIT ?
                    """
                    c.execute(query, (min_chrome_time, limit * 2))

                for u, t in c.fetchall():
                    raw_url = str(u).strip()
                    clean_title = str(t).strip() if t else raw_url

                    clean_url, custom_title = BrowserTabCapture._clean_url(raw_url, clean_title)
                    final_title = custom_title or clean_title

                    # Check noise & privacy filter on sanitized URL
                    if BrowserTabCapture._is_noise_url(clean_url, final_title):
                        continue

                    title_key = final_title.strip().lower()
                    if clean_url not in seen_urls and title_key not in seen_titles:
                        seen_urls.add(clean_url)
                        seen_titles.add(title_key)
                        cat = BrowserTabCapture._categorize_url(clean_url, final_title)
                        urls.append({
                            "url": clean_url,
                            "title": final_title,
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
