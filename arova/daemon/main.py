import multiprocessing
multiprocessing.freeze_support()

import asyncio
import sys
import logging
import uuid
import time
from dataclasses import dataclass
from arova.core.runtime import RuntimeContainer
from arova.core.ipc.uds import UnixSocketTransport
from arova.core.bridge.websocket_manager import WebSocketManager
from arova.core.bridge.runtime_events import RuntimeEventMapper
from arova.core.cognition.ledger import InvestigationLedger
from arova.core.cognition.investigator import ProactiveInvestigator

logging.basicConfig(level=logging.INFO)


class ArovaDaemon:
    def __init__(self):
        self.runtime = None
        import os
        sock_path = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "arova.sock")
        self.transport = UnixSocketTransport(sock_path)
        ws_port = int(os.environ.get("WS_PORT", 8765))
        try:
            from arova.core.config.loader import load_config
            cfg = load_config()
            ws_host = cfg.get("daemon", {}).get("ws_host", "127.0.0.1")
            ws_port_cfg = cfg.get("daemon", {}).get("ws_port")
            if ws_port_cfg:
                ws_port = int(ws_port_cfg)
        except Exception:
            ws_host = "127.0.0.1"
            
        self.ws_manager = WebSocketManager(host=ws_host, port=ws_port)
        
        self.investigation_ledger = InvestigationLedger()
        self.proactive_investigator = ProactiveInvestigator(self.investigation_ledger)
        
        # Keep track of latest telemetry
        self._latest_telemetry = {}


    async def _on_client_message(self, client_id: str, payload: dict):
        import json
        cmd = payload.get("command", "")
        
        if cmd == "environment.snapshot":
            if self.runtime and hasattr(self.runtime, "environment_graph"):
                snap = self.runtime.environment_graph.snapshot()
                trace = self.runtime.environment_graph.get_trace(last_n=10)
                response = json.dumps({"snapshot": snap, "trace": trace}, indent=2, default=str)
                await self.transport.send_message(client_id, response)
            else:
                await self.transport.send_message(client_id, json.dumps({"error": "graph not available"}))
                
        elif cmd == "cognition.snapshot":
            if self.runtime and hasattr(self.runtime, "priority_engine"):
                data = {
                    "priority_engine": self.runtime.priority_engine.get_inspector_state(),
                    "trajectory": {},
                    "modulation": {}
                }
                
                if hasattr(self.runtime, "narrative_generator"):
                    traj = self.runtime.narrative_generator.get_current_trajectory()
                    data["trajectory"] = {
                        "narrative": traj.narrative,
                        "confidence": round(traj.confidence, 3),
                        "probabilities": traj.probabilities,
                        "derived_from": traj.derived_from
                    }
                    
                if hasattr(self.runtime, "presence_modulator"):
                    mod = self.runtime.presence_modulator.get_current_profile()
                    data["modulation"] = {
                        "verbosity": mod.verbosity,
                        "cadence": mod.cadence,
                        "emotional_temperature": mod.emotional_temperature,
                        "interruption_sensitivity": mod.interruption_sensitivity,
                        "ambient_density": mod.ambient_density
                    }
                    
                response = json.dumps(data, indent=2, default=str)
                await self.transport.send_message(client_id, response)
            else:
                await self.transport.send_message(client_id, json.dumps({"error": "cognition not available"}))

    async def _on_ws_message(self, payload: dict):
        if payload.get("type") == "user.message":
            text = payload.get("text", "")
            vocalize = payload.get("vocalize", True)
            mentions = payload.get("mentions", []) or payload.get("mentioned_resources", []) or []
            # Also parse @mentions from text as fallback (@file.py -> mention)
            if not mentions and "@" in text:
                import re
                mentions = re.findall(r'@([\w./\-\\:]+)', text)
            
            if self.runtime and self.runtime.session:
                turn = self.runtime.session.start_new_turn(text)
                turn_id = turn.turn_id
            else:
                turn_id = f"turn_{uuid.uuid4().hex[:8]}"
                
            logging.info(f"Main: Received user.message. Assigned turn_id={turn_id}. text='{text}', vocalize={vocalize}, mentions={mentions}")
            
            # Inject transcript to IntentRuntime — with mentions for grounded @-tag
            payload_dict = {
                "transcript": text,
                "turn_id": turn_id,
                "source": "chat",
                "vocalize": vocalize,
                "mentions": mentions,
                "raw_text": text
            }
            if self.runtime and self.runtime.event_bus:
                logging.info(f"Main: Injecting TRANSCRIPT_FINAL to EventBus for {turn_id}")
                self.runtime.event_bus.emit("voice", "TRANSCRIPT_FINAL", payload_dict)
            else:
                logging.error(f"Main: Cannot inject TRANSCRIPT_FINAL, EventBus missing!")
        elif payload.get("type") == "client.interrupt":
            logging.info("Main: Received client.interrupt via WebSocket.")
            if self.runtime and self.runtime.event_bus:
                self.runtime.event_bus.emit("runtime", "INTERRUPT_REQUESTED", {"source": "ui_command"})
        elif payload.get("type") == "voice.set_mic":
            enabled = payload.get("enabled", True)
            logging.info(f"Main: Received voice.set_mic via WebSocket: enabled={enabled}")
            if self.runtime and hasattr(self.runtime, 'voice_loop') and self.runtime.voice_loop:
                if enabled:
                    self.runtime.voice_loop.start_listening()
                else:
                    self.runtime.voice_loop.stop_listening()
            else:
                logging.error("Main: voice_loop is not available! Voice pipeline may not be initialized.")
        elif payload.get("type") == "client.new_thread":
            logging.info("Main: Received client.new_thread via WebSocket.")
            if self.runtime and self.runtime.session:
                # 1. Save active chat as an organized CognitiveThread before resetting
                msgs = self.runtime.session._legacy_messages
                if msgs:
                    user_msgs = [m for m in msgs if m.get("role") == "user"]
                    first_text = user_msgs[0].get("content", "").strip() if user_msgs else ""
                    thread_title = (first_text[:45] + "...") if len(first_text) > 45 else (first_text or f"Chat Thread {len(self.runtime.session.thread_manager.get_all_threads()) + 1}")
                    
                    thread = self.runtime.session.thread_manager.create_thread(title=thread_title)
                    thread.messages = list(msgs)
                    self.runtime.session.thread_manager.update_thread_state(thread.thread_id, "latent")
                
                # 2. Reset active session messages
                self.runtime.session.clear()
                if self.runtime.session._active_turn:
                    self.runtime.session._archive_turn(self.runtime.session._active_turn)
                    self.runtime.session._active_turn = None
                self.runtime.session.thread_manager._sync()
                self.runtime._persist_runtime()
                
                # 3. Confirm clear state to frontend
                self.ws_manager.broadcast({
                    "v": 1,
                    "type": "session.sync",
                    "messages": []
                })
                self.ws_manager.broadcast({
                    "type": "automation.action_progress",
                    "action": "",
                    "node_state": "completed"
                })
        elif payload.get("type") == "runtime.ping":
            self.ws_manager.broadcast({"v": 1, "type": "runtime.pong", "timestamp": int(time.time() * 1000)})
        elif payload.get("type") == "session.sync_request":
            # Send full state sync
            if self.runtime and self.runtime.session:
                history = [msg for msg in self.runtime.session._legacy_messages]
                self.ws_manager.broadcast({
                    "type": "session.sync",
                    "messages": history
                })
        elif payload.get("type") == "provider.discovery_request":
            from arova.core.config.discovery import ProviderDiscovery
            asyncio.create_task(self._handle_discovery())
        elif payload.get("type") == "provider.test":
            provider_id = payload.get("provider")
            api_key = payload.get("api_key")
            host = payload.get("host", "")
            req_id = payload.get("req_id")
            asyncio.create_task(self._handle_provider_test(provider_id, api_key, host, req_id))
        elif payload.get("type") == "config.get_request":
            from arova.core.config.manager import get_config_manager
            manager = get_config_manager()
            self.ws_manager.broadcast({
                "type": "config.sync",
                "config": manager.load_config(),
                "providers": manager.load_providers()
            })
        elif payload.get("type") == "config.update_request":
            from arova.core.config.manager import get_config_manager
            manager = get_config_manager()
            if "config" in payload:
                manager.save_config(payload["config"])
            if "providers" in payload:
                manager.save_providers(payload["providers"])
            
            # Hot reload provider manager
            if self.runtime and self.runtime.model_runtime and self.runtime.model_runtime.provider_manager:
                self.runtime.model_runtime.provider_manager._discover_and_register()
                active = list(self.runtime.model_runtime.provider_manager.all_providers.keys())
                active = [p for p in active if p != "mock"]
                logging.info(f"Daemon: Hot-reload complete. Active providers: {active}")
                self.ws_manager.broadcast({
                    "type": "provider.reloaded",
                    "active_providers": active
                })
            
            self.ws_manager.broadcast({
                "type": "config.sync",
                "config": manager.load_config(),
                "providers": manager.load_providers()
            })
        elif payload.get("type") in ["workspace.get_request", "workspace.sync_request"]:
            if hasattr(self.runtime, 'workspace_manager'):
                self.runtime.workspace_manager.sync_to_bus()
        elif payload.get("type") == "workspace.get_continue_context":
            if hasattr(self.runtime, 'workspace_manager') and self.runtime.workspace_manager:
                wid = payload.get("workspace_id")
                ctx = self.runtime.workspace_manager.get_continue_context(wid)
                self.ws_manager.broadcast({
                    "v": 1,
                    "type": "workspace.continue_context",
                    "context": ctx
                })
        elif payload.get("type") == "workspace.switch":
            if hasattr(self.runtime, 'workspace_manager'):
                wid = payload.get("workspace_id")
                if wid:
                    self.runtime.workspace_manager.set_active_workspace(wid)
        elif payload.get("type") in ["work.accept", "work.accept_request"]:
            if hasattr(self.runtime, 'workspace_manager') and self.runtime.workspace_manager:
                self.runtime.workspace_manager._on_work_accept(payload)
        elif payload.get("type") in ["work.reject", "work.reject_request"]:
            if hasattr(self.runtime, 'workspace_manager') and self.runtime.workspace_manager:
                self.runtime.workspace_manager._on_work_reject(payload)
        elif payload.get("type") == "workspace.continue":
            if hasattr(self.runtime, 'workspace_manager') and self.runtime.workspace_manager:
                wid = payload.get("workspace_id")
                restore_options = payload.get("options", {})
                if wid:
                    self.runtime.workspace_manager.set_active_workspace(wid)
                active_ws = self.runtime.workspace_manager.get_workspace(wid) if wid else self.runtime.workspace_manager.get_active_workspace()
                if not active_ws:
                    active_ws = self.runtime.workspace_manager.get_workspace("ws_default")
                if active_ws:
                    title = active_ws.title
                    # 1. Restore Environment & emit telemetry
                    self.runtime.workspace_manager.restore_environment(active_ws, restore_options)

                    # 2. Add visual confirmation directly into persistent session history
                    confirm_text = f"Restored {title}. Ready to continue working."
                    if hasattr(self.runtime, 'session') and self.runtime.session:
                        self.runtime.session.add_assistant_message(confirm_text)
                        history = [dict(msg) for msg in self.runtime.session._legacy_messages]
                        self.ws_manager.broadcast({
                            "type": "session.sync",
                            "messages": history
                        })
                    
                    # 3. Clear active action indicator
                    self.ws_manager.broadcast({
                        "type": "automation.action_progress",
                        "action": "",
                        "node_state": "completed"
                    })
                    
                    async def _generate_dynamic_welcome():
                        try:
                            # 4. Prime Cognitive State (Layer 2 Active Workspace Context)
                            summary_prompt = active_ws.get_workspace_summary_prompt() if hasattr(active_ws, 'get_workspace_summary_prompt') else ""
                            if hasattr(self.runtime, 'session') and self.runtime.session:
                                self.runtime.session.set_system_prompt(summary_prompt)

                                decisions_summary = active_ws.understanding.decisions[0] if active_ws.understanding.decisions else "continue this project"
                                next_step_summary = active_ws.understanding.momentum.next_action or "exploring current signals"
                                delta_items = getattr(active_ws.understanding, "delta_changes", [])
                                
                                prompt = f"I have just returned to my workspace '{title}'. "
                                if delta_items:
                                    prompt += f"Since I left, these changes occurred: {', '.join(delta_items)}. "
                                else:
                                    prompt += f"Since I left, {active_ws.understanding.what_changed}. "
                                prompt += f"Yesterday I decided to {decisions_summary}. My next step should be {next_step_summary}. "
                                prompt += "Write a very concise, conversational welcome back message summarizing this and asking if I want to proceed. Avoid markdown lists.\n"

                                from arova.core.models.schema import ReasoningDepth, ReasoningBudget
                                welcome_msg = await self.runtime.model_runtime.generate(
                                    messages=[{"role": "user", "content": prompt}],
                                    system_prompt="You are Arova, an intelligent desktop OS assistant. Be highly concise, human-like, and direct.",
                                    depth=ReasoningDepth.STANDARD,
                                    budget=ReasoningBudget(max_tokens=150)
                                )
                                
                                self.runtime.session.add_assistant_message(welcome_msg.strip())
                                
                                # 5. Sync updated chat feed immediately to frontend
                                history = [dict(msg) for msg in self.runtime.session._legacy_messages]
                                self.ws_manager.broadcast({
                                    "type": "session.sync",
                                    "messages": history
                                })
                        except Exception as e:
                            import logging
                            logging.error(f"Failed to generate dynamic welcome: {e}")
                    
                    asyncio.create_task(_generate_dynamic_welcome())
                    
                    # 6. Visual confirmation toast
                    self.ws_manager.broadcast({
                        "type": "cognition.surfacing_push",
                        "item": {
                            "type": "surfacing",
                            "from": "System",
                            "paragraphs": [
                                f"**Restored: {title}**",
                                f"Primed active AI context & prepared {len(active_ws.reality.resources)} working resources."
                            ],
                            "actions": []
                        }
                    })
        elif payload.get("type") == "awareness.get_request":
            if self.runtime and self.runtime.awareness_manager:
                hidden = self.runtime.awareness_manager.get_currently_hidden()
                visible = []
                if hasattr(self.runtime, 'provider_manager'):
                    visible = await self.runtime.provider_manager.get_visible_context()
                active_ws = self.runtime.workspace_manager.get_active_workspace().to_dict() if hasattr(self.runtime, 'workspace_manager') and self.runtime.workspace_manager.get_active_workspace() else None
                self.ws_manager.broadcast({
                    "type": "awareness.sync",
                    "policy": self.runtime.awareness_manager.policy.to_dict(),
                    "hidden": hidden,
                    "visible": visible,
                    "active_workspace": active_ws
                })
        elif payload.get("type") == "awareness.update_request":
            if self.runtime and self.runtime.awareness_manager:
                layer = payload.get("layer")
                enabled = payload.get("enabled")
                if layer is not None and enabled is not None:
                    self.runtime.awareness_manager.update_layer(layer, enabled)
                
                hidden = self.runtime.awareness_manager.get_currently_hidden()
                visible = []
                if hasattr(self.runtime, 'provider_manager'):
                    visible = await self.runtime.provider_manager.get_visible_context()
                active_ws = self.runtime.workspace_manager.get_active_workspace().to_dict() if hasattr(self.runtime, 'workspace_manager') and self.runtime.workspace_manager.get_active_workspace() else None
                    
                self.ws_manager.broadcast({
                    "type": "awareness.sync",
                    "policy": self.runtime.awareness_manager.policy.to_dict(),
                    "hidden": hidden,
                    "visible": visible,
                    "active_workspace": active_ws
                })
        elif payload.get("type") == "dogfooding.get_dashboard":
            metrics = self.runtime.kpi_collector.get_dogfooding_dashboard_summary() if hasattr(self.runtime, 'kpi_collector') and self.runtime.kpi_collector else {}
            self.ws_manager.broadcast({
                "type": "dogfooding.dashboard",
                "metrics": metrics
            })
        elif payload.get("type") == "dogfooding.get_debug_state":
            captured_events = [e.to_dict() for e in self.runtime.capture_engine._recent_events[-50:]] if hasattr(self.runtime, 'capture_engine') and self.runtime.capture_engine else []
            active_ws = self.runtime.workspace_manager.get_active_workspace() if hasattr(self.runtime, 'workspace_manager') and self.runtime.workspace_manager else None
            active_ws_dict = active_ws.to_dict() if active_ws else {}
            why_chose = active_ws.understanding.explainability_reasons if active_ws and hasattr(active_ws.understanding, 'explainability_reasons') else ["Most active repository activity", "Unresolved blocker observed"]
            search_items = [item.to_dict() for item in self.runtime.search_index.get_all_items()[:50]] if hasattr(self.runtime, 'search_index') and self.runtime.search_index else []
            resources = [r.to_dict() for r in self.runtime.workspace_manager.restoration_engine.resource_registry.all_resources()] if hasattr(self.runtime, 'workspace_manager') and hasattr(self.runtime.workspace_manager, 'restoration_engine') else []
            restore_plan = active_ws_dict.get("last_restore_outcomes", {}) if active_ws_dict else {}
            traffic = {"active_subscribers": len(self.runtime.event_bus._subscribers) if hasattr(self.runtime, 'event_bus') and hasattr(self.runtime.event_bus, '_subscribers') else 0}
            metrics = self.runtime.kpi_collector.get_dogfooding_dashboard_summary() if hasattr(self.runtime, 'kpi_collector') and self.runtime.kpi_collector else {}
            self.ws_manager.broadcast({
                "type": "dogfooding.debug_state",
                "state": {
                    "captured_events": captured_events,
                    "active_workspace": active_ws_dict,
                    "why_chose_workspace": why_chose,
                    "search_index_contents": search_items,
                    "resource_registry": resources,
                    "restore_plan": restore_plan,
                    "event_bus_traffic": traffic,
                    "kpi_metrics": metrics
                }
            })
        elif payload.get("type") == "dogfooding.record_failure":
            if hasattr(self.runtime, 'kpi_collector') and self.runtime.kpi_collector:
                self.runtime.kpi_collector.record_failure_reason(
                    payload.get("reason", "other"),
                    details=payload.get("details", "")
                )
        elif payload.get("type") == "dogfooding.calibrate_confidence":
            if hasattr(self.runtime, 'kpi_collector') and self.runtime.kpi_collector:
                self.runtime.kpi_collector.record_confidence_calibration(
                    int(payload.get("score", 0)),
                    payload.get("rating", "mostly_correct")
                )
        elif payload.get("type") == "dogfooding.record_acceptance":
            if hasattr(self.runtime, 'kpi_collector') and self.runtime.kpi_collector:
                self.runtime.kpi_collector.record_acceptance_event(
                    payload.get("event", "shown")
                )
        elif payload.get("type") == "dogfooding.record_search_analytics":
            if hasattr(self.runtime, 'kpi_collector') and self.runtime.kpi_collector:
                self.runtime.kpi_collector.record_search_analytics(
                    payload.get("query", ""),
                    bool(payload.get("result_clicked", False)),
                    float(payload.get("time_to_click_sec", 0.0)),
                    bool(payload.get("needed_second_search", False))
                )
        elif payload.get("type") == "environment.ignore_app":
            from arova.core.config.manager import get_config_manager
            app_name = payload.get("app_name")
            if app_name:
                manager = get_config_manager()
                cfg = manager.load_config()
                privacy = cfg.setdefault("privacy", {})
                ignored = privacy.setdefault("ignored_apps", [])
                if app_name not in ignored:
                    ignored.append(app_name)
                    manager.save_config(cfg)
                    self.ws_manager.broadcast({
                        "type": "config.sync",
                        "config": cfg,
                        "providers": manager.load_providers()
                    })
        elif payload.get("type") == "momentum.create_capsule":
            if getattr(self.runtime, 'capsule_generator', None) and getattr(self.runtime, 'timeline', None):
                async def _create_cap():
                    capsule = await self.runtime.capsule_generator.generate_capsule(duration_seconds=3600*2) # default to last 2 hours
                    if capsule:
                        self.runtime.timeline.store_capsule(capsule)
                        from dataclasses import asdict
                        self.ws_manager.broadcast({
                            "type": "momentum.capsule_created",
                            "capsule": asdict(capsule)
                        })
                asyncio.create_task(_create_cap())
        elif payload.get("type") == "momentum.get_latest":
            if getattr(self.runtime, 'timeline', None):
                capsule = self.runtime.timeline.get_latest_unresumed_capsule()
                self.ws_manager.broadcast({
                    "type": "momentum.latest_capsule",
                    "capsule": capsule
                })
        elif payload.get("type") == "momentum.resume":
            if getattr(self.runtime, 'timeline', None):
                cap_id = payload.get("capsule_id")
                if cap_id:
                    self.runtime.timeline.mark_capsule_resumed(cap_id)
                    
                    # Fetch capsule to get room and thread details
                    import json
                    try:
                        capsule = None
                        with open(self.runtime.timeline.capsules_path, "r") as f:
                            capsules = json.load(f)
                            for c in capsules:
                                if c.get("id") == cap_id:
                                    capsule = c
                                    break
                    except Exception as e:
                        logging.debug(f"Could not load capsule {cap_id} from plan store: {e}")

                    room_str = capsule.get("room", "Unknown") if capsule else "Unknown"
                    thread_str = "Cognitive Timeline" # Mocked or fetched from active context
                    
                    # Tell frontend to append a message indicating momentum has resumed
                    self.ws_manager.broadcast({
                        "type": "cognition.surfacing_push",
                        "item": {
                            "type": "surfacing",
                            "from": "System",
                            "paragraphs": [
                                "<strong>Momentum resumed</strong>",
                                f"Room: {room_str}<br/>Thread: {thread_str}",
                                "3 new memories surfaced"
                            ],
                            "actions": []
                        }
                    })
        elif payload.get("type") == "momentum.dismiss":
            if getattr(self.runtime, 'timeline', None):
                cap_id = payload.get("capsule_id")
                if cap_id:
                    self.runtime.timeline.mark_capsule_resumed(cap_id)
                    # Clear active attention state / start new thread (factory reset short-term focus only)
                    if hasattr(self.runtime, 'session'):
                        # Example of clearing active room/thread
                        pass
                    self.ws_manager.broadcast({
                        "type": "cognition.surfacing_push",
                        "item": {
                            "type": "surfacing",
                            "from": "System",
                            "paragraphs": [
                                "<strong>Fresh context</strong>",
                                "Active attention cleared. Memory intact."
                            ],
                            "actions": []
                        }
                    })
        elif payload.get("type") == "search.query":
            query = payload.get("query", "")
            kind_filter = payload.get("kind")
            results = []
            if self.runtime and hasattr(self.runtime, "search_index") and self.runtime.search_index:
                if hasattr(self.runtime, "workspace_manager") and self.runtime.workspace_manager.get_active_workspace():
                    self.runtime.search_index.index_workspace(self.runtime.workspace_manager.get_active_workspace())
                items = self.runtime.search_index.search(query, limit=30, kind_filter=kind_filter)
                results = [it.to_dict() for it in items]
            self.ws_manager.broadcast({
                "v": 1,
                "type": "search.results",
                "query": query,
                "results": results
            })
        elif payload.get("type") == "timeline.get_canonical_events":
            limit = payload.get("limit", 100)
            events = []
            if self.runtime and hasattr(self.runtime, "capture_engine") and self.runtime.capture_engine:
                recent = self.runtime.capture_engine.get_recent_events(limit)
                events = [e.to_dict() for e in recent]
            self.ws_manager.broadcast({
                "v": 1,
                "type": "timeline.canonical_events",
                "events": events
            })
        elif payload.get("type") == "memory.query_request":
            if self.runtime and self.runtime.memory_runtime:
                asyncio.create_task(self._handle_memory_query(payload.get("req_id", "")))
        elif payload.get("type") in ["memory.pin", "memory.unpin", "memory.forget", "memory.approve", "memory.reject"]:
            if self.runtime and self.runtime.memory_runtime:
                asyncio.create_task(self._handle_memory_mutate(payload))
        elif payload.get("type") == "memory.set_tier2_policy":
            if self.runtime and self.runtime.memory_runtime:
                mode = payload.get("mode", "review_queue")
                self.runtime.memory_runtime.policy_engine.set_tier2_mode(mode)
                self.ws_manager.broadcast({"type": "memory.policy_updated"})
        elif payload.get("type") in ["journal.entry_added", "journal.add_entry"]:
            asyncio.create_task(self._handle_journal_entry_added(payload))
        elif payload.get("type") in ["journal.query", "journal.get_entries"]:
            asyncio.create_task(self._handle_journal_query(payload))
        elif payload.get("type") == "journal.delete_entry":
            asyncio.create_task(self._handle_journal_delete(payload))
        elif payload.get("type") == "client.resume_thread":
            thread_id = payload.get("thread_id")
            if self.runtime and self.runtime.session and thread_id:
                self.runtime.session.thread_manager.resume_thread(thread_id)
                self.ws_manager.broadcast({
                    "v": 1,
                    "type": "session.sync",
                    "messages": self.runtime.session._legacy_messages
                })
                self.ws_manager.broadcast({"type": "client.thread_resumed", "thread_id": thread_id})
        elif payload.get("type") == "client.delete_thread":
            thread_id = payload.get("thread_id")
            if self.runtime and self.runtime.session and thread_id:
                self.runtime.session.thread_manager.delete_thread(thread_id)
                self.runtime._persist_runtime()
        elif payload.get("type") == "intention.thread_action":
            if getattr(self.runtime, 'event_bus', None):
                self.runtime.event_bus.emit("intention", "THREAD_ACTION_REQUESTED", payload)
                t_id = payload.get("thread_id") or (payload.get("payload") or {}).get("thread_id")
                act = payload.get("action") or (payload.get("payload") or {}).get("action")
                if act == "resume" and t_id and self.runtime and self.runtime.session:
                    self.runtime.session.thread_manager.resume_thread(t_id)
                    self.ws_manager.broadcast({
                        "v": 1,
                        "type": "session.sync",
                        "messages": self.runtime.session._legacy_messages
                    })
                elif act == "delete" and t_id and self.runtime and self.runtime.session:
                    self.runtime.session.thread_manager.delete_thread(t_id)
                    self.runtime._persist_runtime()
        elif payload.get("type") == "timeline.get_request":
            if self.runtime and hasattr(self.runtime, "timeline"):
                asyncio.create_task(self._handle_timeline_query(payload))
        elif payload.get("type") == "diagnostics.poll":
            if self.runtime:
                self.ws_manager.broadcast(self._build_diagnostics_payload())
        elif payload.get("type") == "debug.export_bundle":
            import zipfile, glob, platform
            try:
                out_dir = Path(os.path.expanduser("~/.arova"))
                out_dir.mkdir(parents=True, exist_ok=True)
                zip_path = out_dir / "arova-debug.zip"
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for folder in ["logs", "config", "runtime"]:
                        for p in glob.glob(str(out_dir / folder / "**"), recursive=True):
                            if os.path.isfile(p):
                                zf.write(p, os.path.relpath(p, out_dir))
                    info = f"Version: 0.1.0-beta\nOS: {platform.platform()}\nPython: {platform.python_version()}\nSafe Mode: {'--safe-mode' in sys.argv}"
                    zf.writestr("system_info.txt", info)
                logging.info(f"Exported debug bundle to {zip_path}")
            except Exception as e:
                logging.error(f"Failed to export debug bundle: {e}")
        elif payload.get("type") == "runtime.restart":
            logging.warning("Received runtime.restart request from UI. Shutting down daemon...")
            sys.exit(0) # Supervisor will auto-restart

    def _build_diagnostics_payload(self) -> dict:
        payload = {"type": "diagnostics.sync", "data": {}}
        if not self.runtime:
            return payload
            
        has_active_provider = False
        if hasattr(self.runtime, "model_runtime") and self.runtime.model_runtime:
            pm = getattr(self.runtime.model_runtime, "provider_manager", None)
            if pm and hasattr(pm, "all_providers"):
                has_active_provider = any(k != "mock" for k in pm.all_providers.keys())

        mem_count = 0
        if hasattr(self.runtime, "memory_runtime") and self.runtime.memory_runtime:
            if hasattr(self.runtime.memory_runtime, "storage") and self.runtime.memory_runtime.storage:
                try:
                    import asyncio
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        mem_count = len(self.runtime.memory_runtime.storage.get_all_memories_sync())
                except Exception:
                    mem_count = 0

        payload["data"]["inference"] = {
            "active_provider": has_active_provider,
            "fallbacks": getattr(self.runtime.model_runtime, "_fallback_count", 0) if hasattr(self.runtime, "model_runtime") else 0
        }
        payload["data"]["cognition"] = {
            "active_threads": len(self.runtime.session.thread_manager.get_all_threads()) if self.runtime and self.runtime.session else 0,
            "memory_nodes": mem_count
        }
        payload["data"]["health"] = {
            "ui_running": True,
            "daemon_connected": True,
            "database_ok": hasattr(self.runtime, "memory_runtime") and self.runtime.memory_runtime is not None,
            "memory_loaded": hasattr(self.runtime, "memory_runtime") and getattr(self.runtime.memory_runtime, "storage", None) is not None,
            "workspace_engine_ready": hasattr(self.runtime, "workspace_manager") and self.runtime.workspace_manager is not None,
            "wake_word_ready": hasattr(self.runtime, "voice_service") and self.runtime.voice_service is not None
        }
        return payload

    async def _handle_memory_query(self, req_id: str):
        memories = await self.runtime.memory_runtime.storage.get_all_semantic_memory()
        from dataclasses import asdict
        self.ws_manager.broadcast({
            "type": "memory.query_response",
            "req_id": req_id,
            "memories": [asdict(m) for m in memories]
        })

    async def _handle_memory_mutate(self, payload: dict):
        action = payload.get("type")
        memory_id = payload.get("memory_id")
        mutation_id = payload.get("mutation_id") or f"ui_mut_{uuid.uuid4().hex[:8]}"
        if not memory_id:
            return
        if action == "memory.pin":
            await self.runtime.memory_runtime.storage.pin_semantic_memory(memory_id, mutation_id)
        elif action == "memory.unpin":
            await self.runtime.memory_runtime.storage.unpin_semantic_memory(memory_id, mutation_id)
        elif action == "memory.forget":
            await self.runtime.memory_runtime.storage.delete_semantic_memory(memory_id, mutation_id)
        elif action == "memory.approve":
            # For Tier 3 RAM-only candidates, they come with the full memory payload
            memory_data = payload.get("memory", {})
            duration = payload.get("duration", "permanent") # permanent, 30_days, session_only
            
            if duration == "session_only":
                from arova.core.memory.storage import MemoryEntry
                entry = MemoryEntry(**memory_data)
                entry.approval_state = "session_only"
                self.runtime.memory_runtime.session_only_memories.append(entry)
            else:
                if memory_data:
                    from arova.core.memory.storage import MemoryEntry
                    entry = MemoryEntry(**memory_data)
                    entry.approval_state = "saved"
                    await self.runtime.memory_runtime.storage.store_semantic_memory(entry, mutation_id)
                else:
                    # Approving a pending Tier 2 memory that's already in SQLite
                    query_mem = "UPDATE semantic_memory SET approval_state = 'saved' WHERE id = ?"
                    params_mem = (memory_id,)
                    query_mut = "INSERT INTO memory_mutations (id, memory_id, mutation_type, delta, timestamp) VALUES (?, ?, ?, ?, ?)"
                    import time, json
                    params_mut = (mutation_id, memory_id, "approved", json.dumps({"approval_state": "saved"}), time.time())
                    await self.runtime.memory_runtime.storage._execute_transaction([(query_mem, params_mem), (query_mut, params_mut)])
        elif action == "memory.reject":
            # Just delete it if it was in the DB
            await self.runtime.memory_runtime.storage.delete_semantic_memory(memory_id, mutation_id)
        
        self.ws_manager.broadcast({"type": "memory.mutation_success", "memory_id": memory_id, "action": action})

    async def _handle_journal_entry_added(self, payload: dict):
        entry = payload.get("entry") or {}
        cat = payload.get("category") or entry.get("category", "build")
        text = payload.get("text") or entry.get("content", "")
        e_id = entry.get("id") or f"j_{int(time.time()*1000)}"
        ts = entry.get("timestamp") or time.time() * 1000
        date_str = entry.get("dateStr") or time.strftime("%I:%M %p")
        
        # 1. Persist to ~/.arova/journal/
        journal_dir = Path(os.path.expanduser("~/.arova/journal"))
        journal_dir.mkdir(parents=True, exist_ok=True)
        
        index_file = journal_dir / "journal_index.json"
        existing_entries = []
        if index_file.exists():
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    existing_entries = json.load(f)
            except Exception:
                existing_entries = []
                
        new_record = {
            "id": e_id,
            "timestamp": ts,
            "dateStr": date_str,
            "category": cat,
            "content": text
        }
        existing_entries = [new_record] + [e for e in existing_entries if e.get("id") != e_id]
        with open(index_file, "w", encoding="utf-8") as f:
            json.dump(existing_entries, f, indent=2)
            
        # Write clean daily Markdown file for Notion/Obsidian
        day_filename = time.strftime("%Y-%m-%d") + ".md"
        day_file = journal_dir / day_filename
        cat_labels = {
            "build": "⚡ What I Built",
            "decision": "📐 Architecture Decision",
            "blocker": "⚠️ Blocker & Next Step",
            "reflection": "✨ Daily Reflection"
        }
        header_tag = cat_labels.get(cat, cat.title())
        md_block = f"\n### [{header_tag}] — {date_str}\n*Logged via Arova Dev Journal*\n\n{text}\n\n---\n"
        with open(day_file, "a", encoding="utf-8") as f:
            f.write(md_block)
            
        # 2. Ingest into Semantic Long-Term Memory
        if self.runtime and getattr(self.runtime, 'memory_runtime', None):
            try:
                from arova.core.memory.storage import MemoryEntry
                mem = MemoryEntry(
                    id=e_id,
                    type="journal",
                    content=f"[{cat.upper()}] {text}",
                    source_turn_id=e_id,
                    category=cat,
                    why_remembered="Developer journal reflection and decision log",
                    approval_state="saved",
                    created_at=ts / 1000.0,
                    last_reinforced_at=ts / 1000.0
                )
                await self.runtime.memory_runtime.storage.store_semantic_memory(mem, f"mut_{e_id}")
            except Exception as me_err:
                logging.debug(f"Journal semantic memory storage notice: {me_err}")
                
        # 3. Emit Timeline Event
        if self.runtime and getattr(self.runtime, 'timeline', None):
            try:
                await self.runtime.timeline.record_event(
                    event_type="journal_entry",
                    source="journal",
                    summary=f"Logged journal ({header_tag}): {text[:60]}...",
                    data=new_record
                )
            except Exception:
                pass
                
        self.ws_manager.broadcast({
            "type": "journal.sync",
            "entries": existing_entries
        })

    async def _handle_journal_query(self, payload: dict):
        journal_dir = Path(os.path.expanduser("~/.arova/journal"))
        index_file = journal_dir / "journal_index.json"
        entries = []
        if index_file.exists():
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    entries = json.load(f)
            except Exception:
                entries = []
                
        # Generate smart contextual reflection insights based on active workspace
        ambient_ctx = getattr(getattr(self.runtime, 'ambient_observer', None), 'current_context', None)
        active_app = getattr(ambient_ctx, 'active_app', '') or ''
        active_win = getattr(ambient_ctx, 'window_title', '') or ''
        
        insights = [
            {"id": "ins_1", "text": "What was the most important breakthrough or architectural choice you made today?", "category": "decision"},
            {"id": "ins_2", "text": "Are there any pending blockers or mental loose ends before wrapping up your session?", "category": "blocker"},
            {"id": "ins_3", "text": "Take a breath. Capture what went well and what you want to focus on tomorrow.", "category": "reflection"}
        ]
        
        if "arova" in active_win.lower() or "arova" in active_app.lower():
            insights.insert(0, {
                "id": "ins_ctx",
                "text": "Deep in Arova development — capture recent optimizations and user flows.",
                "category": "build"
            })
            
        self.ws_manager.broadcast({
            "type": "journal.query_response",
            "entries": entries,
            "insights": insights
        })

    async def _handle_journal_delete(self, payload: dict):
        e_id = payload.get("id") or payload.get("entry_id")
        if not e_id:
            return
        journal_dir = Path(os.path.expanduser("~/.arova/journal"))
        index_file = journal_dir / "journal_index.json"
        entries = []
        if index_file.exists():
            try:
                with open(index_file, "r", encoding="utf-8") as f:
                    entries = json.load(f)
                entries = [e for e in entries if e.get("id") != e_id]
                with open(index_file, "w", encoding="utf-8") as f:
                    json.dump(entries, f, indent=2)
            except Exception:
                pass
        
        if self.runtime and getattr(self.runtime, 'memory_runtime', None):
            try:
                await self.runtime.memory_runtime.storage.delete_semantic_memory(e_id, f"del_{e_id}")
            except Exception:
                pass
                
        self.ws_manager.broadcast({
            "type": "journal.sync",
            "entries": entries
        })

    async def _handle_timeline_query(self, payload: dict):
        req_id = payload.get("req_id", "")
        limit = payload.get("limit", 50)
        before = payload.get("before")
        events = await self.runtime.timeline.get_timeline(limit=limit, before_timestamp=before)
        
        self.ws_manager.broadcast({
            "type": "timeline.query_response",
            "req_id": req_id,
            "events": events
        })

    async def _handle_discovery(self):
        from arova.core.config.discovery import ProviderDiscovery
        result = await ProviderDiscovery.run_discovery()
        self.ws_manager.broadcast({
            "type": "provider.discovery",
            "providers": result["providers"],
            "recommended_presence_style": result["recommended_presence_style"]
        })
        
    async def _handle_provider_test(self, provider_id: str, api_key: str, host: str, req_id: str):
        from arova.core.config.discovery import ProviderDiscovery
        result = await ProviderDiscovery.test_provider_connection(provider_id, api_key, host)
        self.ws_manager.broadcast({
            "type": "provider.test_result",
            "req_id": req_id,
            "result": result
        })

    def _cleanup_orphaned_daemon_processes(self, port: int = 8765):
        """Clean up any dangling socket files or orphaned daemon processes holding port 8765."""
        import os
        import signal
        import subprocess
        import time

        xdg_sock = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "arova.sock")
        for sock_file in [xdg_sock, "/tmp/arova.sock", "/var/tmp/arova.sock"]:
            if os.path.exists(sock_file):
                try:
                    os.remove(sock_file)
                    logging.info(f"Cleaned up stale socket file: {sock_file}")
                except Exception as e:
                    logging.warning(f"Could not remove stale socket file {sock_file}: {e}")

        try:
            out = subprocess.check_output(f"fuser {port}/tcp 2>/dev/null || true", shell=True).decode().strip()
            pids = [int(p) for p in out.split() if p.isdigit()]
            current_pid = os.getpid()
            other_pids = [p for p in pids if p != current_pid]
            if other_pids:
                logging.warning(f"Port {port} is held by PID(s) {other_pids}. Cleaning up stale processes...")
                for pid in other_pids:
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except (ProcessLookupError, OSError):
                        pass
                time.sleep(0.3)
                for pid in other_pids:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except (ProcessLookupError, OSError):
                        pass
        except Exception as e:
            logging.warning(f"Port cleanup check returned: {e}")

    async def start(self):
        is_safe_mode = "--safe-mode" in sys.argv
        if is_safe_mode:
            logging.warning(">>> STARTING AROVA DAEMON IN SAFE MODE <<<")
        else:
            logging.info("Starting Arova Daemon...")
        
        self._cleanup_orphaned_daemon_processes()
        self.runtime = RuntimeContainer()
        
        # Start IPC Server
        await self.transport.start_server(self._on_client_message)
        
        # Start WebSocket Bridge
        self.ws_manager.add_message_handler(self._on_ws_message)
        await self.ws_manager.start()


        
        loop = asyncio.get_running_loop()
        
        def _broadcast_event_uds(payload):
            import json
            try:
                msg = json.dumps(payload.__dict__ if hasattr(payload, '__dict__') else payload)
                asyncio.run_coroutine_threadsafe(self.transport.broadcast(msg), loop)
            except Exception as e:
                logging.warning(f"Error broadcasting event over UDS: {e}")
                
        def _broadcast_event_ws(topic, event_type, payload):
            logging.debug(f">>> _broadcast_event_ws ENTERED for {event_type}")
            payload_dict = payload.__dict__ if hasattr(payload, '__dict__') else payload
            if not isinstance(payload_dict, dict):
                payload_dict = {"raw": payload_dict}
            logging.debug(f">>> _broadcast_event_ws MAP for {event_type}, payload_dict: {payload_dict}")
            try:
                external_event = RuntimeEventMapper.map_internal_event(event_type, payload_dict, topic=topic)
                logging.debug(f">>> _broadcast_event_ws MAPPED {event_type} -> {external_event}")
                if external_event:
                    self.ws_manager.broadcast(external_event)
                    logging.debug(f">>> _broadcast_event_ws BROADCAST SUCCESS for {event_type}")
            except Exception as e:
                logging.debug(f">>> _broadcast_event_ws CRASHED: {e}")


        def _make_subscriber(topic, event_type):
            def _handler(payload):
                _broadcast_event_uds(payload)
                _broadcast_event_ws(topic, event_type, payload)
            return _handler

        # Keep strong references to subscribers to prevent weakref garbage collection
        self._ws_subscribers = []
        
        def _subscribe(topic, event_type):
            handler = _make_subscriber(topic, event_type)
            self._ws_subscribers.append(handler)
            self.runtime.event_bus.subscribe(topic, event_type, handler)

        # Subscribe WS and UDS to the event bus
        _subscribe("cognition", "COGNITION_STATE_CHANGED")
        # Voice & Cognition events for the UI
        _subscribe("voice", "TRANSCRIPT_FINAL")
        _subscribe("voice", "PARTIAL_TRANSCRIPT")
        _subscribe("voice", "TEXT_STREAM_STARTED")
        _subscribe("voice", "TTS_STARTED")
        _subscribe("voice", "TTS_COMPLETED")
        _subscribe("voice", "TTS_INTERRUPTED")
        _subscribe("voice", "TEXT_CHUNK_GENERATED")
        _subscribe("voice", "TEXT_RESPONSE_GENERATED")
        _subscribe("cognition", "STREAM_INTERRUPTED")
        _subscribe("memory", "MEMORY_RECALLED")
        _subscribe("timeline", "TIMELINE_EVENT")
        _subscribe("cognition", "PRESENCE_PROFILE_UPDATED")
        _subscribe("cognition", "THREAD_SYNC")

        # Phase 7.5: Memory consent events
        _subscribe("memory", "MEMORY_SAVED")
        _subscribe("memory", "MEMORY_PENDING_REVIEW")
        _subscribe("memory", "MEMORY_SENSITIVE_CANDIDATE")
        _subscribe("memory", "MEMORY_CONTEXTUAL_DIALOG")

        # Environmental events for the UI
        _subscribe("environment", "ATTENTION_STATE_CHANGED")
        _subscribe("environment", "AMBIENT_INTENT_DETECTED")
        _subscribe("ambience", "CONTEXT_CHANGED")
        _subscribe("workspace", "sync")
        _subscribe("capture", "EVENT_INGESTED")
        _subscribe("cognition", "WORKING_MEMORY_CHANGED")
        _subscribe("reasoning", "REASONING_STEP_COMPLETED")

        # Wire VoiceConversationLoop mic state callback to broadcast to UI
        if hasattr(self.runtime, 'voice_loop') and self.runtime.voice_loop:
            def _mic_state_callback(enabled: bool):
                self.ws_manager.broadcast({
                    "type": "voice.mic_state",
                    "enabled": enabled,
                    "listening": enabled
                })
            self.runtime.voice_loop._on_mic_state = _mic_state_callback

        logging.info("Arova Daemon is running.")
        
        # Start proactive investigation loop
        asyncio.create_task(self._proactive_loop())
        
        # Keep alive
        while True:
            await asyncio.sleep(3600)

    async def _handle_timeline_query(self, payload: dict):
        req_id = payload.get("req_id", "")
        limit = payload.get("limit", 50)
        events = await self.runtime.timeline.get_timeline(limit=limit)
        time_insights = self.runtime.timeline.get_time_insights()
        self.ws_manager.broadcast({
            "v": 1,
            "type": "timeline.query_response",
            "req_id": req_id,
            "events": events,
            "time_insights": time_insights
        })

    async def _proactive_loop(self):
        """Background loop that periodically checks telemetry for proactive interventions with CPU-saving idle detection."""
        logging.info("Started proactive investigation loop.")
        last_eval_signature = None
        
        while True:
            await asyncio.sleep(15)  # Check every 15 seconds
            
            # Fetch real ambient context telemetry
            ambient_ctx = getattr(getattr(self.runtime, 'ambient_observer', None), 'current_context', None)
            telemetry = dict(self._latest_telemetry or {})
            if ambient_ctx:
                telemetry.update({
                    "active_app": ambient_ctx.active_app,
                    "window_title": ambient_ctx.window_title,
                    "idle_seconds": ambient_ctx.idle_time_seconds,
                    "open_windows": ambient_ctx.open_windows,
                    "playing_media": ambient_ctx.playing_media
                })
            
            # Skip redundant heavy evaluation if app, window, and media are completely unchanged
            current_signature = (
                telemetry.get("active_app"),
                telemetry.get("window_title"),
                telemetry.get("playing_media"),
                len(telemetry.get("open_windows") or [])
            )
            
            if current_signature == last_eval_signature and (telemetry.get("idle_seconds", 0) > 30):
                continue
                
            last_eval_signature = current_signature
            
            try:
                completed_work = self.proactive_investigator.evaluate_and_investigate(telemetry)
                if completed_work:
                    # Silent surface to UI
                    logging.info(f"Proactive Loop generated work: {completed_work.summary}")
                    if self.runtime and self.runtime.event_bus:
                        self.runtime.event_bus.emit("cognition", "surfacing_push", {
                            "type": "surfacing",
                            "kind": "proactive_investigation",
                            "from": "AROVA · INVESTIGATION",
                            "lede": completed_work.title,
                            "paragraphs": [
                                f"**Summary**: {completed_work.summary}",
                                f"**Evidence**: {len(completed_work.evidence.context_keys)} signals analyzed"
                            ],
                            "actions": [
                                {"label": action.get("label", "Review"), "eventType": "investigation.review", "primary": True}
                                for action in completed_work.suggested_actions
                            ] + [{"label": "Dismiss", "clientAction": "dismiss"}]
                        })
            except Exception as e:
                logging.error(f"Error in proactive loop: {e}")

    def shutdown(self):
        if self.runtime:
            self.runtime.shutdown()

def main():
    daemon = ArovaDaemon()
    try:
        asyncio.run(daemon.start())
    except KeyboardInterrupt:
        daemon.shutdown()

if __name__ == "__main__":
    main()
