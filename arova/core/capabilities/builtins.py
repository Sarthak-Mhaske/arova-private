import asyncio
import logging
from typing import Any, Dict
from arova.core.capabilities.schema import CapabilityDefinition, CapabilityPolicy, CapabilityPermission, ExecutionContext, InterruptBehavior
from arova.core.capabilities.registry import CapabilityRegistry

async def register_builtins(registry: CapabilityRegistry):
    """
    Registers platform-native capabilities built on the pure Platform Abstraction Layer.
    """
    
    async def _execute_shell(args: Dict[str, Any], ctx: ExecutionContext) -> Any:
        command = args.get("command")
        if not command:
            return {"error": "Missing 'command' argument"}
            
        # Arova Capabilities MUST use the governed SystemExecutionLayer
        try:
            returncode, stdout, stderr = await ctx.system.execute(
                command="bash",
                args=["-c", command]
            )
            return {
                "returncode": returncode,
                "stdout": stdout,
                "stderr": stderr
            }
        except Exception as e:
            return {"error": str(e)}

    shell_cap = CapabilityDefinition(
        name="execute_shell",
        description="Executes a sandboxed shell command.",
        parameters_schema={
            "type": "object",
            "properties": {
                "command": {"type": "string"}
            },
            "required": ["command"]
        },
        policy=CapabilityPolicy(
            permission_tier=CapabilityPermission.DANGEROUS,
            timeout_seconds=30.0,
            concurrency_limit=1,
            interrupt_behavior=InterruptBehavior.HARD_CANCEL
        ),
        execute=_execute_shell
    )
    
    await registry.register(shell_cap)
    logging.info("Registered builtin capability: execute_shell")
