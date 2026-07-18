from __future__ import annotations
from typing import Any

from arova.core.transcription_flow import (
    record_and_transcribe,
    transcribe_existing_audio,
)
from arova.core.context import detect_environment
from arova.core.agent import build_system_prompt, run_single_tool_turn_with_followup
from arova.core.tts import speak_text

import re

def parse_fast_command(user_text: str) -> dict[str, Any] | None:
    text = user_text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)
    
    if text in ("stop", "pause"):
        return {"tool_name": "media_control", "tool_args": {"action": text}, "canned_reply": f"{text.capitalize()}d."}
    if text == "play":
        return {"tool_name": "media_control", "tool_args": {"action": "play"}, "canned_reply": "Playing."}
    if text == "next":
        return {"tool_name": "media_control", "tool_args": {"action": "next"}, "canned_reply": "Next track."}
    if text == "previous":
        return {"tool_name": "media_control", "tool_args": {"action": "previous"}, "canned_reply": "Previous track."}
        
    apps = {"kitty", "brave", "firefox", "spotify", "code"}
    for app in apps:
        if text == f"open {app}":
            return {"tool_name": "open_app", "tool_args": {"app_name": app}, "canned_reply": f"{app.capitalize()} opened."}
            
    vol_match = re.match(r'^set volume (\d{1,3})$', text)
    if vol_match:
        return {"tool_name": "set_volume", "tool_args": {"level": vol_match.group(1)}, "canned_reply": f"Volume set to {vol_match.group(1)}%."}
        
    bright_match = re.match(r'^brightness (\d{1,3})$', text)
    if bright_match:
        return {"tool_name": "set_brightness", "tool_args": {"level": bright_match.group(1)}, "canned_reply": f"Brightness set to {bright_match.group(1)}%."}
        
    notify_match = re.match(r'^notify (\w+)$', text)
    if notify_match:
        return {"tool_name": "notify", "tool_args": {"message": notify_match.group(1)}, "canned_reply": "Notification sent."}
        
    return None

def build_voice_user_text(flow_result: dict[str, Any]) -> str:
    """Extract the best text from a transcription flow result to send to the LLM."""
    if not flow_result or not flow_result.get("ok"):
        return ""
        
    en_text = flow_result.get("english_text", "").strip()
    if en_text:
        return en_text
        
    trans_text = flow_result.get("transcription_text", "").strip()
    if trans_text:
        return trans_text
        
    return ""

def get_configured_wake_word(config: dict[str, Any]) -> str:
    return config.get("wake", {}).get("wake_word", "alexa")

def strip_leading_wake_word(text: str, wake_word: str = "alexa") -> str:
    text = text.strip()
    if not wake_word:
        return text
    pattern = r"^" + re.escape(wake_word) + r"[\s,\.!\?]*"
    cleaned = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()
    return cleaned

def should_append_voice_user_message(user_text: str) -> bool:
    return bool(user_text.strip())

def should_append_voice_assistant_message(assistant_text: str) -> bool:
    return bool(assistant_text.strip())

def _build_unified_result(ok: bool, user_text: str, assistant_text: str, trans_res: dict[str, Any] | None, agent_res: dict[str, Any] | None, tts_res: dict[str, Any] | None, error: str | None) -> dict[str, Any]:
    return {
        "ok": ok,
        "user_text": user_text,
        "assistant_text": assistant_text,
        "transcription": trans_res,
        "agent": agent_res,
        "tts": tts_res,
        "error": error
    }

def run_voice_pipeline_from_audio(audio_path: str, config: dict[str, Any], speak_reply: bool = True, state_store: Any | None = None, session: Any | None = None, runtime: Any | None = None) -> dict[str, Any]:
    """Execute the STT -> LLM/Tool -> TTS pipeline from an existing audio file."""
    import threading
    is_ok = False
    try:
        if state_store:
            state_store.set_state("transcribing", "Transcribing audio file...")
            
        # 1. Transcribe
        trans_res = transcribe_existing_audio(audio_path, config, translate_if_needed=True)
        if not trans_res["ok"]:
            if state_store:
                state_store.set_state("error", trans_res.get("error", "Transcription failed"))
            return _build_unified_result(False, "", "", trans_res, None, None, trans_res.get("error", "Transcription failed"))
            
        # 2. Extract Text
        user_text = build_voice_user_text(trans_res)
        wake_word = get_configured_wake_word(config)
        user_text = strip_leading_wake_word(user_text, wake_word)
        if state_store and user_text:
            trunc = user_text[:50] + ("..." if len(user_text) > 50 else "")
            
        if not user_text:
            if state_store:
                state_store.set_state("error", "No text transcribed")
            return _build_unified_result(False, "", "", trans_res, None, None, "No text transcribed")
            
        # 3. Agent Execution
        fast = parse_fast_command(user_text)
        if fast:
            from arova.core.tool_executor import execute_tool
            if state_store:
                state_store.set_state("executing", "Running tool (fast)...")
                
            if session and should_append_voice_user_message(user_text):
                session.add_user_message(user_text)
                
            tool_res = execute_tool(fast["tool_name"], fast["tool_args"], config)
            agent_res = {
                "ok": True,
                "mode": "tool_followup",
                "assistant_content": fast["canned_reply"],
                "tool_name": fast["tool_name"],
                "tool_args": fast["tool_args"],
                "tool_result": tool_res,
                "initial_response": None,
                "final_response": None,
                "error": None,
                "raw": {"initial": None, "final": None}
            }
            if state_store and tool_res.get("ok"):
                state_store.add_activity(f"Executed tool: {fast['tool_name']}")
        else:
            if state_store:
                state_store.set_state("thinking", "Generating response...")
                
            if session and should_append_voice_user_message(user_text):
                session.add_user_message(user_text)
                
            if session:
                if session._system_prompt is None:
                    env = detect_environment()
                    session.set_system_prompt(build_system_prompt(env))
                api_messages = session.build_api_messages()
                sys_prompt = ""
            else:
                env = detect_environment()
                sys_prompt = build_system_prompt(env)
                api_messages = [{"role": "user", "content": user_text}]
            
            agent_res = run_single_tool_turn_with_followup(api_messages, config, system_prompt=sys_prompt)
            
            if state_store and agent_res.get("mode") in ("tool_call", "tool_followup"):
                state_store.set_state("executing", "Running tool...")
            elif state_store and agent_res.get("mode") == "plan_generated":
                state_store.set_state("idle", agent_res.get("assistant_content", ""))
                state_store.set_plan({
                    "goal": agent_res["goal"],
                    "plan": agent_res["plan"],
                    "status": "awaiting_approval"
                })
                
            if not agent_res["ok"]:
                if state_store:
                    state_store.set_state("error", agent_res.get("error", "Agent failed"))
                return _build_unified_result(False, user_text, agent_res.get("assistant_content", ""), trans_res, agent_res, None, agent_res.get("error", "Agent execution failed"))
            
        assistant_text = agent_res.get("assistant_content", "").strip()
        if session and agent_res["ok"] and should_append_voice_assistant_message(assistant_text):
            session.add_assistant_message(assistant_text)
            
        if state_store and agent_res.get("ok"):
            # Log any executed tools
            for et in agent_res.get("executed_tools", []):
                if et.get("tool_result", {}).get("ok"):
                    state_store.add_activity(f"Executed tool: {et['tool_name']}")
            # Log reply
            pass
        
        # 4. TTS Execution
        tts_res = None
        if speak_reply and assistant_text:
            if state_store:
                state_store.set_state("synthesizing", "Synthesizing speech...")
            
            def on_start():
                if state_store:
                    state_store.set_state("speaking", "Speaking out loud...")
                    
            tts_res = speak_text(assistant_text, config, language="english", on_playback_start=on_start)
            if not tts_res["ok"]:
                if state_store:
                    state_store.set_state("error", tts_res.get("error", "TTS failed"))
                return _build_unified_result(False, user_text, assistant_text, trans_res, agent_res, tts_res, tts_res.get("error", "TTS failed"))
            
        is_ok = True
        return _build_unified_result(True, user_text, assistant_text, trans_res, agent_res, tts_res, None)
    except Exception as e:
        if state_store:
            state_store.set_state("error", str(e))
        raise
    finally:
        if state_store:
            if is_ok:
                state_store.set_state("idle", "Completed")
            else:
                threading.Timer(2.0, lambda: state_store.set_state("idle", "")).start()

def run_voice_pipeline(config: dict[str, Any], duration: float | None = None, speak_reply: bool = True, state_store: Any | None = None, session: Any | None = None, runtime: Any | None = None) -> dict[str, Any]:
    """Execute the Record -> STT -> LLM/Tool -> TTS pipeline."""
    import threading
    is_ok = False
    try:
        if state_store:
            state_store.set_state("listening", "Listening to command...")
            
        # 1. Record
        from arova.core.record import record_audio
        rec_res = record_audio(config, duration=duration)
        if not rec_res["ok"]:
            if state_store:
                state_store.set_state("error", rec_res.get("error", "Recording failed"))
            return _build_unified_result(False, "", "", None, None, None, rec_res.get("error", "Recording failed"))
            
        if state_store:
            state_store.set_state("transcribing", "Transcribing audio...")
            
        from arova.core.transcription_flow import transcribe_existing_audio
        trans_res = transcribe_existing_audio(rec_res["audio_path"], config, translate_if_needed=True)
        trans_res["recording_backend"] = rec_res.get("backend")
        
        if not trans_res["ok"]:
            if state_store:
                state_store.set_state("error", trans_res.get("error", "Transcription failed"))
            return _build_unified_result(False, "", "", trans_res, None, None, trans_res.get("error", "Transcription failed"))
            
        # 2. Extract Text
        user_text = build_voice_user_text(trans_res)
        wake_word = get_configured_wake_word(config)
        user_text = strip_leading_wake_word(user_text, wake_word)
        if state_store and user_text:
            trunc = user_text[:50] + ("..." if len(user_text) > 50 else "")
            
        if not user_text:
            if state_store:
                state_store.set_state("error", "No text transcribed")
            return _build_unified_result(False, "", "", trans_res, None, None, "No text transcribed")
            
        # 3. Agent Execution
        fast = parse_fast_command(user_text)
        if fast:
            from arova.core.tool_executor import execute_tool
            if state_store:
                state_store.set_state("executing", "Running tool (fast)...")
                
            if session and should_append_voice_user_message(user_text):
                session.add_user_message(user_text)
                
            tool_res = execute_tool(fast["tool_name"], fast["tool_args"], config)
            agent_res = {
                "ok": True,
                "mode": "tool_followup",
                "assistant_content": fast["canned_reply"],
                "tool_name": fast["tool_name"],
                "tool_args": fast["tool_args"],
                "tool_result": tool_res,
                "initial_response": None,
                "final_response": None,
                "error": None,
                "raw": {"initial": None, "final": None}
            }
            if state_store and tool_res.get("ok"):
                state_store.add_activity(f"Executed tool: {fast['tool_name']}")
        else:
            if state_store:
                state_store.set_state("thinking", "Generating response...")
                
            if session and should_append_voice_user_message(user_text):
                session.add_user_message(user_text)
                
            if session:
                if session._system_prompt is None:
                    env = detect_environment()
                    session.set_system_prompt(build_system_prompt(env))
                api_messages = session.build_api_messages()
                sys_prompt = ""
            else:
                env = detect_environment()
                sys_prompt = build_system_prompt(env)
                api_messages = [{"role": "user", "content": user_text}]
            
            agent_res = run_single_tool_turn_with_followup(api_messages, config, system_prompt=sys_prompt)
            
            if state_store and agent_res.get("mode") in ("tool_call", "tool_followup"):
                state_store.set_state("executing", "Running tool...")
            elif state_store and agent_res.get("mode") == "plan_generated":
                state_store.set_state("idle", agent_res.get("assistant_content", ""))
                state_store.set_plan({
                    "goal": agent_res["goal"],
                    "plan": agent_res["plan"],
                    "status": "awaiting_approval"
                })
                
            if not agent_res["ok"]:
                if state_store:
                    state_store.set_state("error", agent_res.get("error", "Agent failed"))
                return _build_unified_result(False, user_text, agent_res.get("assistant_content", ""), trans_res, agent_res, None, agent_res.get("error", "Agent execution failed"))
            
        assistant_text = agent_res.get("assistant_content", "").strip()
        if session and agent_res["ok"] and should_append_voice_assistant_message(assistant_text):
            session.add_assistant_message(assistant_text)
            
        if state_store and agent_res.get("ok"):
            # Log any executed tools
            for et in agent_res.get("executed_tools", []):
                if et.get("tool_result", {}).get("ok"):
                    state_store.add_activity(f"Executed tool: {et['tool_name']}")
            # Log reply
            pass
        
        # 4. TTS Execution
        tts_res = None
        if speak_reply and assistant_text:
            if state_store:
                state_store.set_state("synthesizing", "Synthesizing speech...")
                
            def on_start2():
                if state_store:
                    state_store.set_state("speaking", "Speaking out loud...")
                    
            audio_manager = runtime.audio_session if runtime else None
            tts_res = speak_text(assistant_text, config, audio_manager=audio_manager, language="english", on_playback_start=on_start2)
            if not tts_res["ok"]:
                if state_store:
                    state_store.set_state("error", tts_res.get("error", "TTS failed"))
                return _build_unified_result(False, user_text, assistant_text, trans_res, agent_res, tts_res, tts_res.get("error", "TTS failed"))
            
        is_ok = True
        return _build_unified_result(True, user_text, assistant_text, trans_res, agent_res, tts_res, None)
    except Exception as e:
        if state_store:
            state_store.set_state("error", str(e))
        raise
    finally:
        if state_store:
            if is_ok:
                state_store.set_state("idle", "Completed")
            else:
                threading.Timer(2.0, lambda: state_store.set_state("idle", "")).start()
