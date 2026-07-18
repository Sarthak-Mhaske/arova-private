import asyncio
import logging
import uuid
import time
from dataclasses import dataclass
from arova.core.runtime import RuntimeContainer
from arova.core.ipc.uds import UnixSocketTransport
from arova.core.bridge.websocket_manager import WebSocketManager
from arova.core.bridge.runtime_events import RuntimeEventMapper

logging.basicConfig(level=logging.INFO)


class ArovaDaemon:
    def __init__(self):
        self.runtime = None
        self.transport = UnixSocketTransport("/tmp/arova.sock")
        self.ws_manager = WebSocketManager(host="localhost", port=8765)

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
            
            if self.runtime and self.runtime.session:
                turn = self.runtime.session.start_new_turn(text)
                turn_id = turn.turn_id
            else:
                turn_id = f"turn_{uuid.uuid4().hex[:8]}"
                
            logging.info(f"Main: Received user.message. Assigned turn_id={turn_id}. text='{text}', vocalize={vocalize}")
            
            # Inject transcript to IntentRuntime
            payload_dict = {
                "transcript": text,
                "turn_id": turn_id,
                "source": "chat",
                "vocalize": vocalize
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
        elif payload.get("type") == "client.new_thread":
            logging.info("Main: Received client.new_thread via WebSocket.")
            if self.runtime and self.runtime.session:
                # Clear hot memory so next input starts fresh
                self.runtime.session._legacy_messages = []
                self.runtime.session._warm_context = []
                if self.runtime.session._active_turn:
                    self.runtime.session._archive_turn(self.runtime.session._active_turn)
                    self.runtime.session._active_turn = None
                self.runtime.session.thread_manager._sync()
                # Persist immediately so restart starts clean
                self.runtime._persist_runtime()
                # Confirm to frontend
                self.ws_manager.broadcast({
                    "v": 1,
                    "type": "session.sync",
                    "messages": []
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
                self.runtime.session.thread_manager._sync()
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
        elif payload.get("type") == "workspace.switch":
            if hasattr(self.runtime, 'workspace_manager'):
                wid = payload.get("workspace_id")
                if wid:
                    self.runtime.workspace_manager.set_active_workspace(wid)
        elif payload.get("type") == "workspace.continue":
            if hasattr(self.runtime, 'workspace_manager'):
                active_ws = self.runtime.workspace_manager.get_active_workspace()
                title = active_ws.title if active_ws else "Arova Development"
                self.ws_manager.broadcast({
                    "type": "cognition.surfacing_push",
                    "item": {
                        "type": "surfacing",
                        "from": "System",
                        "paragraphs": [
                            f"<strong>Continuing: {title}</strong>",
                            "Cognitive context and living momentum are ready."
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
                    except Exception:
                        pass

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
        elif payload.get("type") == "client.resume_thread":
            thread_id = payload.get("thread_id")
            if self.runtime and self.runtime.session and thread_id:
                self.runtime.session.thread_manager.resume_thread(thread_id)
                self.ws_manager.broadcast({"type": "client.thread_resumed", "thread_id": thread_id})
        elif payload.get("type") == "intention.thread_action":
            if getattr(self.runtime, 'event_bus', None):
                self.runtime.event_bus.emit("intention", "THREAD_ACTION_REQUESTED", payload)
        elif payload.get("type") == "timeline.get_request":
            if self.runtime and hasattr(self.runtime, "timeline"):
                asyncio.create_task(self._handle_timeline_query(payload))
        elif payload.get("type") == "diagnostics.poll":
            if self.runtime:
                self.ws_manager.broadcast(self._build_diagnostics_payload())

    def _build_diagnostics_payload(self) -> dict:
        payload = {"type": "diagnostics.sync", "data": {}}
        if not self.runtime:
            return payload
            
        payload["data"]["inference"] = {
            "active_provider": self.runtime.model_runtime.provider_manager.get("groq") is not None, # Simplified
            "fallbacks": getattr(self.runtime.model_runtime, "_fallback_count", 0)
        }
        payload["data"]["cognition"] = {
            "active_threads": len(self.runtime.session.thread_manager.get_all_threads()) if self.runtime.session else 0,
            "memory_nodes": 0 # We'll just fetch this if needed
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

    async def start(self):
        logging.info("Starting Arova Daemon...")
        
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
            except Exception:
                pass
                
        def _broadcast_event_ws(topic, event_type, payload):
            print(f">>> _broadcast_event_ws ENTERED for {event_type}")
            payload_dict = payload.__dict__ if hasattr(payload, '__dict__') else payload
            if not isinstance(payload_dict, dict):
                payload_dict = {"raw": payload_dict}
            print(f">>> _broadcast_event_ws MAP for {event_type}, payload_dict: {payload_dict}")
            try:
                external_event = RuntimeEventMapper.map_internal_event(event_type, payload_dict)
                print(f">>> _broadcast_event_ws MAPPED {event_type} -> {external_event}")
                if external_event:
                    self.ws_manager.broadcast(external_event)
                    print(f">>> _broadcast_event_ws BROADCAST SUCCESS for {event_type}")
            except Exception as e:
                print(f">>> _broadcast_event_ws CRASHED: {e}")

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
        _subscribe("voice", "TRANSCRIPT_FINAL")
        _subscribe("voice", "TEXT_STREAM_STARTED")
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

        logging.info("Arova Daemon is running.")
        
        # Keep alive
        while True:
            await asyncio.sleep(3600)

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
