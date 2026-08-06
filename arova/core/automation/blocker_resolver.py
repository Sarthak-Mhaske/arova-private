import re
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class BlockerResolver:
    """
    Proactive Terminal & Build Blocker Resolver for Arova.
    Inspects command outputs for build/compiler errors (TS17008, TS2304, TS2451, Python NameError)
    and generates 1-click in-chat action fix pills.
    """
    @classmethod
    def analyze_output(cls, command: str, output: str) -> Optional[Dict[str, Any]]:
        if not output:
            return None

        # 1. TypeScript Duplicate Declaration (TS2451)
        ts2451_match = re.search(r"error TS2451: Cannot redeclare block-scoped variable '([^']+)'.*?in ([^\s:]+):(\d+)", output, re.DOTALL)
        if ts2451_match:
            var_name = ts2451_match.group(1)
            file_path = ts2451_match.group(2)
            line_no = ts2451_match.group(3)
            return {
                "error_type": "TS2451",
                "summary": f"Duplicate variable declaration '{var_name}' in {file_path}:{line_no}",
                "actions": [
                    {
                        "label": f"Auto-Fix Duplicate '{var_name}' in {file_path}",
                        "primary": True,
                        "eventType": "user.message",
                        "eventPayload": {"text": f"fix duplicate variable {var_name} in {file_path}", "vocalize": True}
                    }
                ]
            }

        # 2. TypeScript Missing Name / Identifier (TS2304 / TS2552)
        ts2304_match = re.search(r"error TS2304: Cannot find name '([^']+)'.*?in ([^\s:]+):(\d+)", output, re.DOTALL)
        if ts2304_match:
            symbol = ts2304_match.group(1)
            file_path = ts2304_match.group(2)
            line_no = ts2304_match.group(3)
            return {
                "error_type": "TS2304",
                "summary": f"Missing identifier '{symbol}' in {file_path}:{line_no}",
                "actions": [
                    {
                        "label": f"Auto-Declare '{symbol}' in {file_path}",
                        "primary": True,
                        "eventType": "user.message",
                        "eventPayload": {"text": f"declare missing identifier {symbol} in {file_path}", "vocalize": True}
                    }
                ]
            }

        # 3. Python ImportError / NameError
        py_match = re.search(r"(NameError|ImportError|ModuleNotFoundError): (.*)", output)
        if py_match:
            err_type = py_match.group(1)
            err_detail = py_match.group(2)
            return {
                "error_type": err_type,
                "summary": f"Python {err_type}: {err_detail}",
                "actions": [
                    {
                        "label": f"Auto-Fix {err_type}",
                        "primary": True,
                        "eventType": "user.message",
                        "eventPayload": {"text": f"fix {err_type} {err_detail}", "vocalize": True}
                    }
                ]
            }

        return None
