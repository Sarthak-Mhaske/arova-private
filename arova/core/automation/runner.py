import asyncio
import logging
import time
from typing import Dict, Any, Optional
from arova.core.events import RuntimeEventBus, EventPayload
from arova.core.automation.graph import GraphDefinition, GraphExecutionSnapshot, NodeCheckpoint, NodeState

class GraphRunner:
    """
    Traverses the ExecutionGraph deterministically.
    Dispatches nodes to the CapabilityRuntime and maintains execution checkpoints.
    """
    def __init__(self, event_bus: RuntimeEventBus, graph: GraphDefinition, execution_id: str, initial_snapshot: Optional[GraphExecutionSnapshot] = None):
        self.event_bus = event_bus
        self.graph = graph
        self.execution_id = execution_id
        
        # Soft Resumability: Load from prior snapshot or create a new one
        if initial_snapshot:
            self.snapshot = initial_snapshot
        else:
            self.snapshot = GraphExecutionSnapshot(
                execution_id=self.execution_id,
                graph_id=self.graph.id,
                state="running"
            )
            # Initialize all nodes as pending if not in snapshot
            for node in self.graph.nodes:
                if node.id not in self.snapshot.node_checkpoints:
                    self.snapshot.node_checkpoints[node.id] = NodeCheckpoint(node_id=node.id, state=NodeState.PENDING)
                    
        self._node_map = {n.id: n for n in self.graph.nodes}
        self._running = False
        self._task = None
        self._node_completions: Dict[str, asyncio.Event] = {n.id: asyncio.Event() for n in self.graph.nodes}
        
        # Hydrate events for already completed nodes (resumability)
        for nid, chk in self.snapshot.node_checkpoints.items():
            if chk.state in (NodeState.COMPLETED, NodeState.SKIPPED):
                self._node_completions[nid].set()

    def start(self):
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._run_graph())

    def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()

    async def _run_graph(self):
        logging.info(f"GraphRunner started for {self.execution_id} (Graph: {self.graph.id})")
        self.event_bus.emit("automation", "GRAPH_EXECUTION_STARTED", {
            "execution_id": self.execution_id,
            "graph_id": self.graph.id,
            "snapshot": self.snapshot.__dict__
        })
        
        try:
            # Dispatch all nodes concurrently. Each node waits for its dependencies.
            tasks = []
            for node in self.graph.nodes:
                chk = self.snapshot.node_checkpoints[node.id]
                if chk.state == NodeState.PENDING or (chk.state == NodeState.FAILED and chk.retry_count < node.max_retries):
                    tasks.append(asyncio.create_task(self._execute_node(node.id)))
                    
            if tasks:
                await asyncio.gather(*tasks)
                
            # Check overall status
            failed = any(c.state == NodeState.FAILED for c in self.snapshot.node_checkpoints.values())
            self.snapshot.state = "failed" if failed else "completed"
            
            logging.info(f"GraphRunner finished for {self.execution_id} with state: {self.snapshot.state}")
            self.event_bus.emit("automation", "GRAPH_EXECUTION_COMPLETED", {
                "execution_id": self.execution_id,
                "graph_id": self.graph.id,
                "state": self.snapshot.state,
                "snapshot": self.snapshot.__dict__
            })
            
        except asyncio.CancelledError:
            logging.info(f"GraphRunner cancelled for {self.execution_id}")
            self.snapshot.state = "cancelled"

    async def _execute_node(self, node_id: str):
        node = self._node_map[node_id]
        
        # Wait for dependencies
        for dep_id in node.depends_on:
            await self._node_completions[dep_id].wait()
            # If dependency failed/skipped, we might need to skip this node
            dep_chk = self.snapshot.node_checkpoints[dep_id]
            if dep_chk.state == NodeState.FAILED:
                self._update_checkpoint(node_id, NodeState.SKIPPED, error=f"Dependency {dep_id} failed")
                self._node_completions[node_id].set()
                return

        # Check condition (very naive for Phase 6 scaffold)
        if node.condition:
            # We would evaluate against global_outputs or previous node outputs
            # For now, we assume true if not empty
            pass

        chk = self.snapshot.node_checkpoints[node_id]
        
        while chk.retry_count <= node.max_retries and self._running:
            self._update_checkpoint(node_id, NodeState.EXECUTING)
            
            try:
                # We emit DISPATCHED so PolicyRuntime can intercept before CapabilityRuntime
                # Since we don't have a direct async return from EventBus in this scaffold,
                # we'll use a Future to wait for CAPABILITY_EXECUTION_COMPLETED/FAILED
                
                result = await self._dispatch_and_wait(node)
                self._update_checkpoint(node_id, NodeState.COMPLETED, outputs=result)
                self.snapshot.global_outputs[node_id] = result
                break
                
            except Exception as e:
                chk.retry_count += 1
                self._update_checkpoint(node_id, NodeState.FAILED, error=str(e))
                if chk.retry_count <= node.max_retries:
                    logging.warning(f"Node {node_id} failed, retrying ({chk.retry_count}/{node.max_retries})...")
                    await asyncio.sleep(1.0)
                
        self._node_completions[node_id].set()

    async def _dispatch_and_wait(self, node) -> Dict[str, Any]:
        """Dispatches to PolicyRuntime -> CapabilityRuntime and waits for the outcome event."""
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        
        # A unique execution ID for this specific capability invocation
        cap_exec_id = f"{self.execution_id}_{node.id}"
        
        def _on_completed(payload: EventPayload):
            if getattr(payload, "execution_id") == cap_exec_id and not future.done():
                future.set_result(getattr(payload, "result", {}))
                
        def _on_failed(payload: EventPayload):
            if getattr(payload, "execution_id") == cap_exec_id and not future.done():
                future.set_exception(RuntimeError(getattr(payload, "error", "Unknown error")))

        self.event_bus.subscribe("capabilities", "CAPABILITY_EXECUTION_COMPLETED", _on_completed)
        self.event_bus.subscribe("capabilities", "CAPABILITY_EXECUTION_FAILED", _on_failed)
        
        # PolicyRuntime intercepts this
        self.event_bus.emit("policy", "CAPABILITY_EXECUTION_DISPATCHED", {
            "execution_id": cap_exec_id,
            "capability_name": node.capability_name,
            "args": node.args,
            "client_id": "automation_runtime"
        })
        
        try:
            # We wait for the capability to complete, fail, or hit our own hard timeout
            return await asyncio.wait_for(future, timeout=60.0)
        finally:
            self.event_bus.unsubscribe("capabilities", "CAPABILITY_EXECUTION_COMPLETED", _on_completed)
            self.event_bus.unsubscribe("capabilities", "CAPABILITY_EXECUTION_FAILED", _on_failed)

    def _update_checkpoint(self, node_id: str, state: NodeState, outputs: dict = None, error: str = None):
        chk = self.snapshot.node_checkpoints[node_id]
        chk.state = state
        chk.timestamp = time.time()
        if outputs:
            chk.outputs = outputs
        if error:
            chk.error = error
        self.snapshot.updated_at = time.time()
        
        # In a real system, we would immediately flush self.snapshot to MemoryRuntime here
        # to guarantee strict resumability. For now, it stays in memory (soft resumability).
