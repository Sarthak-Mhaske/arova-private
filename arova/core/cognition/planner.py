import uuid
import json
from typing import List, Dict, Any, Optional
from arova.core.models.runtime import ModelRuntime
from arova.core.models.schema import ReasoningDepth, ReasoningBudget
from arova.core.cognition.context import CognitiveContext
from arova.core.automation.graph import GraphDefinition, ExecutionNode

class CognitivePlanner:
    """
    Translates LLM intent into a governed ExecutionGraph.
    The LLM outputs a CognitivePlan JSON, which this parses and converts
    into strict ExecutionNodes for the AutomationRuntime.
    """
    def __init__(self, model_runtime: ModelRuntime):
        self.models = model_runtime
        
    async def generate_graph(self, 
                             messages: List[Dict[str, Any]], 
                             context: CognitiveContext,
                             budget: ReasoningBudget) -> Optional[GraphDefinition]:
                                 
        sys_prompt = (
            "You are the Cognitive Planner for Arova. The user has requested an action.\n"
            "Generate a declarative execution plan. You do not execute tools directly.\n"
            "Output JSON ONLY matching this exact schema:\n"
            "{\n"
            "  \"plan_name\": \"Brief description\",\n"
            "  \"nodes\": [\n"
            "    {\n"
            "      \"id\": \"unique_node_id\",\n"
            "      \"capability_name\": \"name_of_tool\",\n"
            "      \"args\": {\"arg1\": \"value\"},\n"
            "      \"depends_on\": [\"other_node_id\"]\n"
            "    }\n"
            "  ]\n"
            "}\n\n"
            f"{context.to_system_prompt_block()}"
        )
        
        # We use DEEP depth for planning
        res = await self.models.invoke_structured(
            messages=messages,
            system_prompt=sys_prompt,
            depth=ReasoningDepth.DEEP,
            budget=budget
        )
        
        if "error" in res:
            return None
            
        nodes = []
        for n in res.get("nodes", []):
            nodes.append(ExecutionNode(
                id=n.get("id", str(uuid.uuid4())),
                capability_name=n.get("capability_name", ""),
                args=n.get("args", {}),
                depends_on=n.get("depends_on", [])
            ))
            
        return GraphDefinition(
            id=str(uuid.uuid4()),
            name=res.get("plan_name", "Cognitive Plan"),
            nodes=nodes
        )
