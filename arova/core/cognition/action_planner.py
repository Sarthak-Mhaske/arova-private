import uuid
import json
import logging
from typing import List, Dict, Any, Optional
from arova.core.models.runtime import ModelRuntime
from arova.core.models.schema import ReasoningDepth, ReasoningBudget
from arova.core.cognition.context import CognitiveContext
from arova.core.automation.graph import GraphDefinition, ExecutionNode
from arova.core.automation.schema import CapabilityRegistry

logger = logging.getLogger(__name__)

class ActionPlanner:
    """
    LLM-driven tool selection for fast, multi-tool action execution.
    Takes user intent and available tools, outputs a list of tool calls + natural language summary.
    """
    def __init__(self, model_runtime: ModelRuntime):
        self.models = model_runtime
        self.registry = CapabilityRegistry()
        
    async def generate_action_plan(self, 
                                   messages: List[Dict[str, Any]], 
                                   context: CognitiveContext,
                                   budget: ReasoningBudget) -> Optional[tuple[GraphDefinition, str]]:
                                       
        available_caps = self.registry.get_capabilities()
        
        # Build tool definitions block
        tools_block = "AVAILABLE CAPABILITIES:\n"
        if available_caps.get("open_app"):
            tools_block += "- capability: \"open_app\", args: {\"app_name\": \"name of application, OR domain URL (e.g. 'zomato.com', 'gmail.com')\"}\n"
        if available_caps.get("terminal", True):
            tools_block += "- capability: \"run_command\", args: {\"command\": \"shell command string to execute on system\"}\n"
        if available_caps.get("list_open_apps"):
            tools_block += "- capability: \"list_open_apps\", args: {}\n"
        if available_caps.get("focus_window"):
            tools_block += "- capability: \"focus_window\", args: {\"window_name\": \"exact or partial name of the app\"}\n"
        if available_caps.get("close_window"):
            tools_block += "- capability: \"close_window\", args: {\"window_name\": \"exact or partial name of the app\"}\n"
        if available_caps.get("analyze_screen"):
            tools_block += "- capability: \"analyze_screen\", args: {\"query\": \"What specific information are you looking for on the screen?\"}\n"
        if available_caps.get("open_path", True):
            tools_block += "- capability: \"open_path\", args: {\"path\": \"absolute path to the folder or file\"}\n"
        if available_caps.get("search_web"):
            tools_block += "- capability: \"search_web\", args: {\"query\": \"search query text\"}\n"
        if available_caps.get("set_volume"):
            tools_block += "- capability: \"set_volume\", args: {\"level\": 50}\n"
        if available_caps.get("media_control"):
            tools_block += "- capability: \"media_control\", args: {\"command\": \"play_pause\", \"next_track\": \"\", \"previous_track\": \"\", \"stop\": \"\"}\n"
        if available_caps.get("play_music", True):
            tools_block += "- capability: \"play_music\", args: {\"song_query\": \"name of the song and artist\"}\n"
        if available_caps.get("screenshot", True):
            tools_block += "- capability: \"screenshot\", args: {}\n"
            
        import os, sys
        user_home = os.path.expanduser("~")
        current_os = sys.platform

        sys_prompt = (
            "You are the Action Planner for Arova. The user wants to execute simple or complex multi-step actions.\n"
            f"SYSTEM ENVIRONMENT (CRITICAL): OS='{current_os}', USER_HOME='{user_home}'.\n"
            "PATH RULES (CRITICAL):\n"
            f"- ALWAYS use '{user_home}' or '~/' for paths (e.g. '~/PythonLearning' or '{user_home}/PythonLearning').\n"
            "- NEVER use hardcoded '/Users/username' or '/home/username' paths.\n"
            "CONVERSATION CONTEXT RESOLUTION:\n"
            "- The conversation history is provided below. USE IT to resolve pronouns and back-references.\n"
            "- If the user says 'search it', 'open it', 'do it', 'that', 'those' — look at the PREVIOUS messages to determine WHAT 'it' refers to.\n"
            "- If the user says 'open the video you recommended' — find the specific URL from previous assistant response and use it.\n"
            "- If the user says 'open that folder', 'open the folder you created', 'open it in vs code', 'open that project' — find the created folder path (e.g. '~/PythonLearning') in previous messages and use `open_app` with payload `{\"app_name\": \"code ~/PythonLearning\"}` or `open_path` with `{\"path\": \"~/PythonLearning\"}`.\n"
            "- NEVER use literal pronouns ('it', 'that', 'this') as search queries or app names.\n"
            "COMPLEX ACTION WORKFLOW TEMPLATES (UNIVERSAL FOR LINUX, MACOS & WINDOWS):\n"
            "- Creating a folder with learning materials and opening it in VS Code:\n"
            "  Step 1: run_command -> `python3 -c \"import os; p=os.path.expanduser('~/PythonLearning'); os.makedirs(p, exist_ok=True); open(os.path.join(p, 'main.py'), 'w').write('# Python Starter Script\\nprint(\\\"Hello Python!\\\")\\n'); open(os.path.join(p, 'README.md'), 'w').write('# Python Learning Roadmap\\n\\n1. Syntax & Variables\\n2. Control Flow & Loops\\n3. Functions & OOP\\n')\"`\n"
            "  Step 2: open_app -> `{\"app_name\": \"code ~/PythonLearning\"}` (or `run_command` -> `code ~/PythonLearning`).\n"
            "DEEP REASONING & INTENT DISCOVERY:\n"
            "- For web platforms, services, or websites (e.g., 'zomato', 'github', 'linkedin', 'chatgpt'): pass the domain URL in `open_app` `app_name`.\n"
            "- For desktop applications installed on OS (e.g., 'vscode', 'brave', 'discord', 'terminal'): pass the local app name (e.g. 'code', 'brave').\n"
            "- For installing VS Code extensions: combine all requested extensions into ONE single `run_command` step: `code --install-extension ms-python.python --install-extension ms-python.pylint --install-extension ms-toolsai.jupyter --install-extension formulahendry.code-runner`.\n"
            "- Verified VS Code Extension IDs: `ms-python.python` (Python), `ms-python.pylint` (Pylint), `ms-toolsai.jupyter` (Jupyter), `formulahendry.code-runner` (Code Runner), `ms-vscode.cpptools` (C/C++), `esbenp.prettier-vscode` (Prettier). NEVER guess fake publisher IDs.\n"
            "- For searching specific topics or questions: use `search_web`.\n"
            "- For executing shell commands, system scripts, or diagnostics: use `run_command` with payload `{\"command\": \"...\"}`.\n"
            "DATA PIPING: If an action requires information generated by a previous action, use `{{step_id.output}}` in payload arguments to inject that data.\n"
            f"{tools_block}\n"
            "Output JSON ONLY matching this exact schema:\n"
            "{\n"
            "  \"feedback_message\": \"Natural language message describing what you have done\",\n"
            "  \"nodes\": [\n"
            "    {\n"
            "      \"id\": \"step_1\",\n"
            "      \"capability_name\": \"name_of_capability\",\n"
            "      \"args\": {\"arg1\": \"value\"}\n"
            "    }\n"
            "  ]\n"
            "}\n\n"
            f"{context.to_system_prompt_block()}"
        )
        
        # We use FAST depth for action planning to minimize latency
        res = await self.models.invoke_structured(
            messages=messages,
            system_prompt=sys_prompt,
            depth=ReasoningDepth.FAST,
            budget=budget
        )
        
        if not res.get("nodes") and "content" in res and isinstance(res["content"], str):
            raw_text = res["content"]
            if "{" in raw_text and "}" in raw_text:
                try:
                    extracted = json.loads(raw_text[raw_text.find("{"):raw_text.rfind("}")+1])
                    if isinstance(extracted, dict) and extracted.get("nodes"):
                        res = extracted
                except Exception as ex:
                    logger.debug(f"ActionPlanner raw content extraction failed: {ex}")

        if "error" in res or not res.get("nodes"):
            logger.warning(f"ActionPlanner failed to generate valid nodes or returned error. Raw response: {res}")
            return None
            
        nodes = []
        for n in res.get("nodes", []):
            if "capability_name" in n:
                nodes.append(ExecutionNode(
                    id=n.get("id", str(uuid.uuid4())),
                    capability_name=n["capability_name"],
                    args=n.get("args", {})
                ))
                
        if not nodes:
            return None

        # Safeguard 1: Gratitude / Acknowledgement messages must NEVER execute actions
        latest_user_text = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                latest_user_text = m.get("content", "").lower()
                break

        pleasantry_signals = [
            "thanks", "thank you", "dhanyavad", "shukriya", "good job", "awesome", 
            "sounds good", "looks good", "no thanks", "thats all", "that's all", "nothing else",
            "theek hai", "ok thanks", "okay thanks", "got it"
        ]
        action_keywords = ["play ", "open ", "search ", "run ", "close ", "kill ", "set volume", "launch ", "code "]
        is_pleasantry = any(p in latest_user_text for p in pleasantry_signals)
        has_new_action = any(c in latest_user_text for c in action_keywords)
        
        if is_pleasantry and not has_new_action:
            logger.info("ActionPlanner: Query is gratitude/acknowledgement without new action command. Rejecting action graph to fall back to Chat.")
            return None

        # Safeguard 2: If the user is asking for advice, roadmaps, or learning strategy (e.g., "make a plan", "what if I watch"),
        # and the ActionPlanner generated open_app/search_web nodes without explicit user command words ("open", "launch", "search"),
        # reject the action plan so it falls back to Chat for a full conversational response.
        advice_signals = ["roadmap", "make a plan", "study plan", "how to start", "what if i", "which sequence", "recommend", "advice"]
        explicit_cmd_signals = ["open ", "launch ", "search for ", "google ", "go to ", "run ", "play "]
        
        is_advice_query = any(s in latest_user_text for s in advice_signals)
        has_explicit_cmd = any(s in latest_user_text for s in explicit_cmd_signals)
        only_opening_links = all(n.capability_name in ("open_app", "search_web") for n in nodes)

        if is_advice_query and only_opening_links and not has_explicit_cmd:
            logger.info("ActionPlanner: Query is an advice/roadmap question without explicit 'open' commands. Rejecting action graph to fall back to Chat path.")
            return None

        graph = GraphDefinition(
            id=str(uuid.uuid4()),
            name="LLM Action Plan",
            nodes=nodes
        )
        
        feedback = res.get("feedback_message", "Executing actions...")
        return graph, feedback
