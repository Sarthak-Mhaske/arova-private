from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import time
from enum import Enum

class NodeState(str, Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class NodeCheckpoint:
    node_id: str
    state: NodeState
    outputs: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    retry_count: int = 0
    timestamp: float = field(default_factory=time.time)

@dataclass
class ExecutionNode:
    id: str
    capability_name: str
    args: Dict[str, Any] = field(default_factory=dict)
    
    # DAG topology
    depends_on: List[str] = field(default_factory=list)
    
    # Resilience/Restart semantics
    resumable: bool = False
    idempotent: bool = True
    max_retries: int = 0
    
    # Conditional branching (simple string eval for Phase 6)
    condition: Optional[str] = None

@dataclass
class GraphDefinition:
    id: str
    name: str
    nodes: List[ExecutionNode] = field(default_factory=list)

@dataclass
class GraphExecutionSnapshot:
    execution_id: str
    graph_id: str
    state: str = "running" # running, completed, failed
    node_checkpoints: Dict[str, NodeCheckpoint] = field(default_factory=dict)
    global_outputs: Dict[str, Any] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
