# recording tools - record and replay browser action sequences
import json

from src.tools.base import ToolBase


class RecordingTools(ToolBase):
    """tools for recording and replaying browser action sequences"""

    def _register_tools(self) -> None:
        """register recording tools"""
        self._mcp.tool()(self.start_recording)
        self._mcp.tool()(self.stop_recording)
        self._mcp.tool()(self.replay_action_sequence)

    async def start_recording(self) -> str:
        """Start recording browser actions for later replay.

        All subsequent browser actions (navigate, click, type, etc.) will be
        recorded until stop_recording is called.
        """
        self.session.start_recording()
        return "Recording started. All browser actions will be captured."

    async def stop_recording(self) -> str:
        """Stop recording and return the recorded action sequence as JSON.

        The returned JSON can be saved and passed to replay_action_sequence later.
        """
        actions = self.session.stop_recording()
        if not actions:
            return "No actions were recorded."
        return (
            f"Recorded {len(actions)} action(s):\n"
            f"{json.dumps(actions, indent=2)}"
        )

    async def replay_action_sequence(self, sequence: str) -> str:
        """Replay a previously recorded action sequence.

        Args:
            sequence: JSON string of recorded actions from stop_recording
        """
        import src.tools as tools_module

        try:
            actions = json.loads(sequence)
        except json.JSONDecodeError as e:
            return f"Invalid JSON: {e}"

        if not actions:
            return "Empty action sequence."

        results = []
        for i, entry in enumerate(actions):
            action = entry.get("action", "")
            params = entry.get("params", {})

            func = getattr(tools_module, action, None)
            if func is None:
                results.append(f"  {i+1}. SKIP: Unknown action '{action}'")
                continue

            try:
                result = await func(**params)
                # Truncate long results
                result_str = str(result)
                if len(result_str) > 100:
                    result_str = result_str[:100] + "..."
                results.append(f"  {i+1}. {action}: {result_str}")
            except Exception as e:
                results.append(f"  {i+1}. {action}: ERROR - {str(e)}")

        return f"Replayed {len(actions)} action(s):\n" + "\n".join(results)
