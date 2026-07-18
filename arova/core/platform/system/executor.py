import asyncio
import logging
from typing import Optional, Dict, Any, Tuple

class SystemExecutionLayer:
    """
    Centralized point for all OS-level execution.
    Capabilities MUST use this instead of raw subprocess.run.
    Handles timeouts, cancellation, telemetry, and isolation.
    """
    def __init__(self):
        # We can track active system processes here
        self._active_processes: Dict[str, asyncio.subprocess.Process] = {}
        
    async def execute(self, 
                      command: str, 
                      args: list[str], 
                      timeout_seconds: float = 30.0,
                      capture_output: bool = True,
                      cwd: Optional[str] = None) -> Tuple[int, str, str]:
        """
        Executes a command cooperatively.
        Returns (returncode, stdout, stderr).
        """
        logging.info(f"SystemExecutor: Running '{command} {' '.join(args)}'")
        
        try:
            process = await asyncio.create_subprocess_exec(
                command, *args,
                stdout=asyncio.subprocess.PIPE if capture_output else None,
                stderr=asyncio.subprocess.PIPE if capture_output else None,
                cwd=cwd
            )
            
            proc_id = str(id(process))
            self._active_processes[proc_id] = process
            
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), 
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                logging.warning(f"SystemExecutor: Command '{command}' timed out after {timeout_seconds}s")
                process.terminate()
                await process.wait()
                raise
            except asyncio.CancelledError:
                logging.warning(f"SystemExecutor: Command '{command}' was cancelled.")
                process.terminate()
                await process.wait()
                raise
            finally:
                self._active_processes.pop(proc_id, None)
                
            stdout = stdout_bytes.decode().strip() if stdout_bytes else ""
            stderr = stderr_bytes.decode().strip() if stderr_bytes else ""
            
            return process.returncode, stdout, stderr
            
        except Exception as e:
            logging.error(f"SystemExecutor: Failed to execute '{command}': {e}")
            raise
