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
                # Copy to temp file to avoid locking issues while browser is open
                tmp_fd, tmp_path = tempfile.mkstemp(suffix=".sqlite")
                os.close(tmp_fd)
                shutil.copy2(path, tmp_path)

                conn = sqlite3.connect(tmp_path)
                c = conn.cursor()

                if "places.sqlite" in path:
                    # Firefox schema
                    query = """
                    SELECT url, title FROM moz_places 
                    WHERE url LIKE 'http%' AND title IS NOT NULL AND title != ''
                    ORDER BY last_visit_date DESC LIMIT ?
                    """
                else:
                    # Chromium / Chrome / Brave / Edge schema
                    query = """
                    SELECT url, title FROM urls 
                    WHERE url LIKE 'http%' AND title IS NOT NULL AND title != ''
                    ORDER BY last_visit_time DESC LIMIT ?
                    """

                c.execute(query, (limit,))
                for u, t in c.fetchall():
                    clean_url = str(u).strip()
                    clean_title = str(t).strip() if t else clean_url
                    # Skip generic login/oauth redirect URLs
                    if any(skip in clean_url for skip in ["/accounts/SetOSID", "/ServiceLogin", "oauth", "authuser"]):
                        continue
                    if clean_url not in seen_urls:
                        seen_urls.add(clean_url)
                        urls.append({
                            "url": clean_url,
                            "title": clean_title
                        })
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
