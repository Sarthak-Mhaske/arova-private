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

        # 1. Port In Use / Address Already In Use (Errno 98 / EADDRINUSE)
        port_match = re.search(r"(?:Errno 98|EADDRINUSE|address already in use).*?(\d{4,5})", output, re.IGNORECASE)
        if not port_match:
            port_match = re.search(r"(\d{4,5}).*?(?:in use|already in use)", output, re.IGNORECASE)
        if port_match:
            port_num = port_match.group(1)
            return {
                "error_type": "PortInUse",
                "summary": f"Port {port_num} already in use (Address already in use / Errno 98)",
                "actions": [
                    {
                        "label": f"Free Port {port_num} & Retry",
                        "primary": True,
                        "eventType": "user.message",
                        "eventPayload": {"text": f"free port {port_num} and restart service", "vocalize": True}
                    }
                ]
            }

        # 2. Git Merge Conflict
        git_conflict = re.search(r"CONFLICT \((?:content|modify/delete|add/add)\): Merge conflict in ([^\n]+)", output)
        if git_conflict:
            file_name = git_conflict.group(1).strip()
            return {
                "error_type": "GitMergeConflict",
                "summary": f"Git merge conflict in {file_name}",
                "actions": [
                    {
                        "label": f"Resolve Conflict in {file_name}",
                        "primary": True,
                        "eventType": "user.message",
                        "eventPayload": {"text": f"inspect and resolve merge conflict in {file_name}", "vocalize": True}
                    }
                ]
            }

        # 3. TypeScript Duplicate Declaration (TS2451)
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

        # 4. TypeScript Missing Name / Identifier (TS2304 / TS2552)
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

        # 5. Python File Traceback with specific error (e.g. File "...", line X \n ...Error)
        py_traceback = re.search(r'File "([^"]+)", line (\d+).*?\n(?:[^\n]*\n)?(UnboundLocalError|NameError|ImportError|ModuleNotFoundError|SyntaxError|TypeError|AttributeError|IndentationError|ValueError|KeyError): (.*)', output, re.DOTALL)
        if py_traceback:
            file_path = py_traceback.group(1)
            line_no = py_traceback.group(2)
            err_type = py_traceback.group(3)
            err_detail = py_traceback.group(4).strip()
            return {
                "error_type": err_type,
                "summary": f"{err_type} in {file_path}:{line_no} — {err_detail}",
                "file": file_path,
                "line": int(line_no),
                "actions": [
                    {
                        "label": f"Auto-Fix {err_type} in {file_path.split('/')[-1]}",
                        "primary": True,
                        "eventType": "user.message",
                        "eventPayload": {"text": f"fix {err_type} at line {line_no} in {file_path}: {err_detail}", "vocalize": True}
                    }
                ]
            }

        # 6. Python / Node general error match
        py_match = re.search(r"(UnboundLocalError|NameError|ImportError|ModuleNotFoundError|SyntaxError|TypeError|ReferenceError|AssertionError|AttributeError|IndentationError): (.*)", output)
        if py_match:
            err_type = py_match.group(1)
            err_detail = py_match.group(2).strip()
            return {
                "error_type": err_type,
                "summary": f"{err_type}: {err_detail}",
                "actions": [
                    {
                        "label": f"Auto-Fix {err_type}",
                        "primary": True,
                        "eventType": "user.message",
                        "eventPayload": {"text": f"fix {err_type} {err_detail}", "vocalize": True}
                    }
                ]
            }

        # 7. Rust Compiler Error (error[E0...]: ...)
        rust_match = re.search(r"error\[(E\d+)\]: (.*)", output)
        if rust_match:
            err_code = rust_match.group(1)
            err_msg = rust_match.group(2).strip()
            return {
                "error_type": f"Rust {err_code}",
                "summary": f"Rust Compiler error [{err_code}]: {err_msg}",
                "actions": [
                    {
                        "label": f"Auto-Fix Rust Error {err_code}",
                        "primary": True,
                        "eventType": "user.message",
                        "eventPayload": {"text": f"fix rust error {err_code} {err_msg}", "vocalize": True}
                    }
                ]
            }

        # 8. Vite / Webpack / Next.js Build Failure
        build_match = re.search(r"\[vite\]\s*(?:Internal server error|error):\s*(.*)", output) or re.search(r"Failed to compile\.\s*\n(.*)", output)
        if build_match:
            detail = build_match.group(1).strip()
            return {
                "error_type": "BuildError",
                "summary": f"Build Failure: {detail}",
                "actions": [
                    {
                        "label": "Auto-Fix Build Error",
                        "primary": True,
                        "eventType": "user.message",
                        "eventPayload": {"text": f"diagnose and fix build error: {detail}", "vocalize": True}
                    }
                ]
            }

        # 9. Generic TypeScript / Compiler Error Fallback
        generic_ts = re.search(r"error (TS\d+): (.*)", output)
        if generic_ts:
            code = generic_ts.group(1)
            msg = generic_ts.group(2).strip()
            return {
                "error_type": code,
                "summary": f"Compiler {code}: {msg}",
                "actions": [
                    {
                        "label": f"Auto-Fix Compiler Error {code}",
                        "primary": True,
                        "eventType": "user.message",
                        "eventPayload": {"text": f"fix compiler error {code} {msg}", "vocalize": True}
                    }
                ]
            }

        return None
