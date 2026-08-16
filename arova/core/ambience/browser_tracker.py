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
    # Dangerous / Sensitive categories that should NEVER be captured or restored
    CRITICAL_PRIVACY_PATTERNS = [
        # 1. Banking, Payments, and Crypto/Trading
        "bank", "paypal.com", "stripe.com", "razorpay.com", "chase.com", "wellsfargo.com",
        "zerodha.com", "groww.in", "hdfcbank.com", "icicibank.com", "sbi.co.in", "checkout", "billing", "payment",
        # 2. Authentication, Credential Resets & Secrets
        "password", "reset_password", "two-factor", "2fa", "accounts.google.com/signin",
        "/setosid", "/servicelogin", "token=", "session_token=",
        # 3. Sensitive Personal (Health, Tax, Legal, Govt IDs)
        "tax", "irs.gov", "incometax", "aadhaar", "passport", "health", "medical",
        # 4. Search Engine Noise & Captchas
        "google.com/search", "google.com/sorry", "bing.com/search", "duckduckgo.com/?q=", "recaptcha", "cloudflare.com",
        # 5. Social Media Entertainment & Distractions
        "instagram.com", "tiktok.com", "facebook.com", "twitter.com", "x.com", "pinterest.com"
    ]

    @classmethod
    def _is_noise_url(cls, url: str, title: str) -> bool:
        url_lower = url.lower()
        title_lower = title.lower()

        # Strict Critical Privacy and Noise check
        if any(pat in url_lower or pat in title_lower for pat in cls.CRITICAL_PRIVACY_PATTERNS):
            return True

        # Pure raw IPs without port/app
        if url_lower.rstrip('/') in ["http://127.0.0.1", "http://localhost"]:
            return True

        return False

    @staticmethod
    def _clean_url(url: str, title: str = "") -> tuple:
        """
        Strips tracking bloat and normalizes communication/collaboration web apps
        to privacy-safe, clean top-level URLs without deep message IDs or sensitive tokens.
        Returns (clean_url, optional_sanitized_title).
        """
        import urllib.parse
        try:
            parsed = urllib.parse.urlparse(url)
            netloc = parsed.netloc.lower()
            path = parsed.path.lower()

            # 1. Communication & Collaboration Apps (Sanitize to clean top-level web app)
            if "mail.google.com" in netloc:
                return "https://mail.google.com/mail/u/0/", "Gmail"
            if "web.whatsapp.com" in netloc:
                return "https://web.whatsapp.com/", "WhatsApp Web"
            if "outlook.live.com" in netloc or "outlook.office.com" in netloc or "outlook.office365.com" in netloc:
                return "https://outlook.live.com/mail/", "Outlook"
            if "web.telegram.org" in netloc:
                return "https://web.telegram.org/", "Telegram Web"
            if "meet.google.com" in netloc:
                clean_path = parsed.path.split('?')[0]
                return f"https://meet.google.com{clean_path}", "Google Meet"
            if "zoom.us" in netloc and "/j/" in path:
                return f"https://zoom.us{parsed.path.split('?')[0]}", "Zoom Meeting"
            if "app.slack.com" in netloc:
                return f"https://app.slack.com{parsed.path.split('?')[0]}", "Slack"
            if "discord.com" in netloc:
                return "https://discord.com/app", "Discord"
            if "teams.microsoft.com" in netloc or "teams.live.com" in netloc:
                return "https://teams.microsoft.com/", "Microsoft Teams"

            # 2. General URLs: strip tracking query parameters
            qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=False)
            filtered_qs = {
                k: v for k, v in qs.items() 
                if not any(k.startswith(p) or k == p for p in ["gs_lcrp", "google_abuse", "sei", "sourceid", "oq", "sclient", "utm_source", "utm_medium", "utm_campaign", "pli", "authuser", "ref", "fbclid"])
            }
            new_query = urllib.parse.urlencode(filtered_qs, doseq=True)
            clean = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
            return clean.rstrip('?'), None
        except Exception:
            return url, None

    @staticmethod
    def _categorize_url(url: str, title: str) -> str:
        text = f"{url} {title}".lower()
        if any(k in text for k in ["mail.google.com", "web.whatsapp.com", "meet.google.com", "slack.com", "discord.com", "teams.microsoft.com", "zoom.us", "telegram.org", "outlook.live.com"]):
            return "communication"
        if any(k in text for k in ["youtube.com/watch", "youtu.be", "tutorial", "learn", "course", "docs", "documentation", "arxiv", "paper", "medium.com", "dev.to", "wikipedia"]):
            return "study"
        if any(k in text for k in ["github.com", "gitlab.com", "localhost", "stack overflow", "stackoverflow.com", "api", "dashboard", "jira", "confluence", "linear.app", "notion.so"]):
            return "development"
        return "general"

    @staticmethod
    def get_recent_browser_history(limit: int = 10, max_age_hours: float = 12.0) -> List[Dict[str, str]]:
        """
        Extracts genuine browser tabs visited during the current/last active work session (default: last 12 hours).
        Converts browser-specific epoch timestamps and strictly filters out stale history.
        """
        urls: List[Dict[str, str]] = []
        seen_urls = set()
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
                    if clean_url not in seen_urls:
                        seen_urls.add(clean_url)
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
