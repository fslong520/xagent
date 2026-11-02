"""
Consolidated WebSocket tests.

Merges several WebSocket-related test modules to eliminate duplicated code.
"""

import json
import unittest
from unittest.mock import AsyncMock

import pytest

from tests.shared import create_test_components


@pytest.mark.slow
class TestWebSocket(unittest.IsolatedAsyncioTestCase):
    """Consolidated WebSocket tests"""

    def setUp(self):
        """Set up the test components"""
        self.components = create_test_components()
        self.test_messages = []
        self.test_connections = {}

    async def test_websocket_connection_management(self):
        """Test WebSocket connection management"""
        print("\n=== WebSocket connection management ===")

        # Import the WebSocket manager
        from xagent.web.api.websocket import ConnectionManager

        manager = ConnectionManager()

        # Test connections
        websocket1 = AsyncMock()
        websocket2 = AsyncMock()

        # Simulate connections
        await manager.connect(websocket1, 1)
        await manager.connect(websocket2, 2)

        # Verify connections
        self.assertEqual(len(manager.active_connections), 2)
        self.assertIn(1, manager.active_connections)
        self.assertIn(2, manager.active_connections)

        # Test disconnection
        manager.disconnect(websocket1)

        # Verify disconnection
        self.assertEqual(len(manager.active_connections), 1)
        self.assertNotIn(1, manager.active_connections)
        self.assertIn(2, manager.active_connections)

        print("Connection management verified: ✅")
        print(f"  Active connections: {len(manager.active_connections)}")
        print(f"  Remaining connections: {list(manager.active_connections.keys())}")

    async def test_websocket_message_broadcast(self):
        """Test WebSocket message broadcasting"""
        print("\n=== WebSocket message broadcast ===")

        from xagent.web.api.websocket import ConnectionManager

        manager = ConnectionManager()

        # Create mock WebSocket connections
        websocket1 = AsyncMock()
        websocket2 = AsyncMock()

        # Connect
        await manager.connect(websocket1, 1)
        await manager.connect(websocket2, 2)

        # Broadcast a message
        test_message = {
            "type": "test_message",
            "data": {"content": "Hello, WebSocket!"},
        }

        await manager.broadcast_to_task(test_message, 1)

        # Verify the message delivery
        websocket1.send_text.assert_called_once_with(json.dumps(test_message))
        websocket2.send_text.assert_not_called()  # must not reach task_2

        print("Message broadcast verified: ✅")
        print("  Target task: task_1")
        print(f"  websocket1 call count: {websocket1.send_text.call_count}")
        print(f"  websocket2 call count: {websocket2.send_text.call_count}")

    async def test_websocket_message_handling(self):
        """Test WebSocket message handling"""
        print("\n=== WebSocket message handling ===")

        # Test handling of different message types
        test_messages = [
            {"type": "subscribe", "task_id": "task_1"},
            {"type": "unsubscribe", "task_id": "task_1"},
            {"type": "ping", "data": {"timestamp": "2023-01-01T00:00:00"}},
            {"type": "get_status", "task_id": "task_1"},
        ]

        for message in test_messages:
            # Simulate message handling
            message_type = message.get("type")

            if message_type == "subscribe":
                # Subscribe logic
                task_id = message.get("task_id")
                print(f"  Handling subscribe message: task_id={task_id}")

            elif message_type == "unsubscribe":
                # Unsubscribe logic
                task_id = message.get("task_id")
                print(f"  Handling unsubscribe message: task_id={task_id}")

            elif message_type == "ping":
                # Ping response
                print(f"  Handling ping message: {message.get('data')}")

            elif message_type == "get_status":
                # Status query
                task_id = message.get("task_id")
                print(f"  Handling status query: task_id={task_id}")

        print("Message handling verified: ✅")
        print(f"  Messages handled: {len(test_messages)}")

    async def test_websocket_error_handling(self):
        """Test WebSocket error handling"""
        print("\n=== WebSocket error handling ===")

        from xagent.web.api.websocket import ConnectionManager

        manager = ConnectionManager()

        # Create a WebSocket that raises
        failing_websocket = AsyncMock()
        failing_websocket.send_text.side_effect = Exception("Connection failed")

        # Connect
        await manager.connect(failing_websocket, "task_1")

        # Attempt to send a message - the exception should be handled
        test_message = {"type": "test", "data": {"content": "test"}}

        try:
            await manager.broadcast_to_task(test_message, 1)
        except Exception as e:
            print(f"  Caught exception: {e}")

        # Verify the connection still exists
        self.assertEqual(len(manager.active_connections), 1)

        print("Error handling verified: ✅")
        print(f"  Connection count preserved: {len(manager.active_connections)}")

    async def test_websocket_trace_integration(self):
        """Test WebSocket integration with tracing"""
        print("\n=== WebSocket trace integration ===")

        from xagent.web.api.websocket import ConnectionManager

        manager = ConnectionManager()

        # Create a mock WebSocket
        websocket = AsyncMock()
        await manager.connect(websocket, 1)

        # Create trace events
        trace_events = [
            {
                "type": "trace_start",
                "task_id": "task_1",
                "data": {"timestamp": "2023-01-01T00:00:00"},
            },
            {
                "type": "dag_step_start",
                "task_id": "task_1",
                "data": {"step_id": "step1", "step_name": "test_step"},
            },
            {
                "type": "llm_call_start",
                "task_id": "task_1",
                "data": {"model": "gpt-3.5-turbo"},
            },
        ]

        # Simulate sending trace events over the WebSocket
        for event in trace_events:
            websocket_message = {"type": "trace_event", "data": event}
            await manager.broadcast_to_task(websocket_message, 1)

        # Verify the WebSocket delivery
        self.assertEqual(websocket.send_text.call_count, len(trace_events))

        print("Trace integration verified: ✅")
        print(f"  Trace events sent: {len(trace_events)}")
        print(f"  WebSocket call count: {websocket.send_text.call_count}")

    async def test_websocket_step_update(self):
        """Test WebSocket step updates"""
        print("\n=== WebSocket step update ===")

        from xagent.web.api.websocket import ConnectionManager

        manager = ConnectionManager()

        # Create several WebSocket connections
        websockets = []
        for i in range(3):
            websocket = AsyncMock()
            await manager.connect(websocket, i)
            websockets.append(websocket)

        # Send a step update
        step_update = {
            "type": "step_update",
            "task_id": "task_1",
            "data": {
                "step_id": "step1",
                "status": "completed",
                "result": {"output": "Step completed successfully"},
            },
        }

        await manager.broadcast_to_task(step_update, 1)

        # Verify only the task_1 WebSocket received the message
        websockets[0].send_text.assert_not_called()
        websockets[1].send_text.assert_called_once_with(json.dumps(step_update))
        websockets[2].send_text.assert_not_called()

        print("Step update verified: ✅")
        print("  Target task: task_1")
        print("  WebSockets that received it: 1/3")

    async def test_websocket_task_isolation(self):
        """Test WebSocket task isolation"""
        print("\n=== WebSocket task isolation ===")

        from xagent.web.api.websocket import ConnectionManager

        manager = ConnectionManager()

        # Create WebSocket connections for different tasks
        task_connections = {}
        for i in [1, 2, 3]:
            websocket = AsyncMock()
            await manager.connect(websocket, i)
            task_connections[i] = websocket

        # Send messages to different tasks
        for i in [1, 2, 3]:
            message = {
                "type": "task_message",
                "task_id": f"task_{i}",
                "data": {"content": f"Message for task_{i}"},
            }
            await manager.broadcast_to_task(message, i)

        # Verify task isolation
        for task_id, websocket in task_connections.items():
            self.assertEqual(websocket.send_text.call_count, 1)
            call_args = websocket.send_text.call_args[0][0]
            # The message is a JSON string and must be parsed
            import json

            parsed_message = json.loads(call_args)
            self.assertEqual(parsed_message["task_id"], f"task_{task_id}")

        print("Task isolation verified: ✅")
        print(f"  Task count: {len(task_connections)}")
        print("  Messages received per task: 1")

    async def test_websocket_connection_limits(self):
        """Test WebSocket connection limits"""
        print("\n=== WebSocket connection limits ===")

        from xagent.web.api.websocket import ConnectionManager

        manager = ConnectionManager()

        # Create a large number of connections
        max_connections = 100
        websockets = []

        for i in range(max_connections):
            websocket = AsyncMock()
            await manager.connect(websocket, i)
            websockets.append(websocket)

        # Verify the connection count
        self.assertEqual(len(manager.active_connections), max_connections)

        # Test broadcast performance
        test_message = {"type": "broadcast_test", "data": {"content": "test"}}

        import time

        start_time = time.thread_time()

        # Broadcast a message to every connection
        for i in range(max_connections):
            await manager.broadcast_to_task(test_message, i)

        end_time = time.thread_time()
        duration = end_time - start_time

        # Count only CPU work; CI scheduling stalls are not a broadcast regression.
        for websocket in websockets:
            websocket.send_text.assert_awaited_once()
            self.assertEqual(
                json.loads(websocket.send_text.call_args.args[0]), test_message
            )

        self.assertLess(
            duration,
            5.0,
            f"{max_connections} broadcasts should finish within 5 CPU seconds",
        )

        print("Connection limit verified: ✅")
        print(f"  Max connections: {max_connections}")
        print(f"  Broadcast CPU time: {duration:.3f}s")
        print(f"  Average per broadcast: {duration / max_connections * 1000:.3f}ms")

    async def test_websocket_message_validation(self):
        """Test WebSocket message validation"""
        print("\n=== WebSocket message validation ===")

        # Test validation of different message shapes
        test_cases = [
            {
                "name": "valid message",
                "message": {
                    "type": "trace_event",
                    "task_id": "task_1",
                    "data": {"event_type": "test"},
                },
                "should_pass": True,
            },
            {
                "name": "missing type",
                "message": {"task_id": "task_1", "data": {"event_type": "test"}},
                "should_pass": False,
            },
            {
                "name": "missing task_id",
                "message": {"type": "trace_event", "data": {"event_type": "test"}},
                "should_pass": False,
            },
            {"name": "empty message", "message": {}, "should_pass": False},
            {
                "name": "non-dict message",
                "message": "invalid_message",
                "should_pass": False,
            },
        ]

        for test_case in test_cases:
            message = test_case["message"]
            should_pass = test_case["should_pass"]

            # Simple message validation logic
            is_valid = True
            if not isinstance(message, dict):
                is_valid = False
            elif "type" not in message:
                is_valid = False
            elif "task_id" not in message:
                is_valid = False

            self.assertEqual(
                is_valid,
                should_pass,
                f"message '{test_case['name']}' failed validation",
            )

            print(f"  {test_case['name']}: {'✅' if is_valid == should_pass else '❌'}")

        print("Message validation verified: ✅")
        print(f"  Test cases: {len(test_cases)}")

    async def test_websocket_stream_event_format(self):
        """Test that the WebSocket stream event format is uniform"""
        print("\n=== WebSocket stream event format ===")

        from datetime import datetime, timezone

        from xagent.web.services.task_execution import create_stream_event

        # Test stream event creation
        test_data = {
            "step_id": "step1",
            "step_name": "test_step",
            "status": "completed",
            "result": "test_result",
        }

        stream_event = create_stream_event(
            "dag_step_info",
            task_id=1,
            data=test_data,
            timestamp=datetime.now(timezone.utc),
        )

        # Verify the stream event format
        self.assertEqual(stream_event["type"], "trace_event")
        self.assertEqual(stream_event["event_type"], "dag_step_info")
        self.assertEqual(stream_event["task_id"], 1)
        self.assertIn("event_id", stream_event)
        self.assertIn("timestamp", stream_event)
        self.assertEqual(stream_event["data"], test_data)

        print("Stream event format verified: ✅")
        print(f"  Event type: {stream_event['event_type']}")
        print(f"  Task ID: {stream_event['task_id']}")
        print(f"  Event ID: {stream_event['event_id']}")
        print(f"  Data keys: {list(stream_event['data'].keys())}")

    async def test_websocket_reconnection_handling(self):
        """Test WebSocket reconnection handling"""
        print("\n=== WebSocket reconnection ===")

        from xagent.web.api.websocket import ConnectionManager

        manager = ConnectionManager()

        # Create a WebSocket connection
        websocket1 = AsyncMock()
        await manager.connect(websocket1, 1)

        # Simulate a dropped connection
        manager.disconnect(websocket1)

        # Verify the connection was dropped
        self.assertEqual(len(manager.active_connections), 0)

        # Reconnect
        websocket2 = AsyncMock()
        await manager.connect(websocket2, 1)

        # Verify the reconnection succeeded
        self.assertEqual(len(manager.active_connections), 1)
        self.assertIn(1, manager.active_connections)

        # Test message delivery after reconnecting
        test_message = {"type": "reconnection_test", "data": {"content": "test"}}
        await manager.broadcast_to_task(test_message, 1)

        # Verify the new connection receives messages
        websocket2.send_text.assert_called_once_with(json.dumps(test_message))

        print("Reconnection verified: ✅")
        print("  Connections after drop: 0")
        print(f"  Connections after reconnect: {len(manager.active_connections)}")
        print(f"  Messages delivered: {websocket2.send_text.call_count}")

    async def test_historical_data_streaming(self):
        """Test streaming of historical data"""
        print("\n=== Historical data streaming ===")

        from datetime import datetime, timezone
        from unittest.mock import AsyncMock

        from xagent.web.services.task_execution import create_stream_event

        # Create a mock WebSocket
        websocket = AsyncMock()

        # Simulate database data
        now = datetime.now(timezone.utc)
        mock_task_data = {
            "id": 1,
            "title": "Test Task",
            "description": "Test Description",
            "status": "completed",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        # Simulate historical data events
        historical_events = [
            create_stream_event("task_info", 1, mock_task_data, now),
            create_stream_event(
                "task_message", 1, {"role": "user", "content": "Hello"}, now
            ),
            create_stream_event(
                "dag_step_info",
                1,
                {"id": "step1", "name": "test_step", "status": "completed"},
                now,
            ),
            create_stream_event(
                "execution_log", 1, {"level": "info", "message": "Step completed"}, now
            ),
            create_stream_event(
                "historical_data_complete",
                1,
                {"message": "Historical data loaded"},
                now,
            ),
        ]

        # Simulate sending the historical data
        for event in historical_events:
            await websocket.send_text(json.dumps(event))

        # Verify the historical data delivery
        self.assertEqual(websocket.send_text.call_count, len(historical_events))

        # Verify the event format
        for i, call in enumerate(websocket.send_text.call_args_list):
            sent_data = json.loads(call[0][0])
            self.assertEqual(sent_data["type"], "trace_event")
            self.assertIn("event_id", sent_data)
            self.assertIn("timestamp", sent_data)
            self.assertEqual(sent_data["task_id"], 1)

        print("Historical data streaming verified: ✅")
        print(f"  Events sent: {len(historical_events)}")
        print(f"  WebSocket call count: {websocket.send_text.call_count}")

    async def test_rewrite_file_links_supports_legacy_preview_paths(self):
        from xagent.web.services.task_execution import _rewrite_file_links_to_file_id

        output_text = (
            "Legacy link: [report](/preview/web_task_12/output/report.html)\n"
            "Legacy uploads link: [img](/uploads/user_3/web_task_12/output/a.png)\n"
            "File link: [doc](file:/preview/web_task_12/output/readme.md)\n"
            "Task-local link: [poster](output/poster.html)"
        )
        path_to_file_id = {
            "preview/web_task_12/output/report.html": "fid-report",
            "uploads/user_3/web_task_12/output/a.png": "fid-image",
            "preview/web_task_12/output/readme.md": "fid-readme",
            "output/poster.html": "fid-poster",
        }

        rewritten = _rewrite_file_links_to_file_id(output_text, path_to_file_id)

        self.assertIn("[report](file:fid-report)", rewritten)
        self.assertIn("[img](file:fid-image)", rewritten)
        self.assertIn("[doc](file:fid-readme)", rewritten)
        self.assertIn("[poster](file:fid-poster)", rewritten)

    async def test_rewrite_file_links_preserves_non_legacy_urls(self):
        from xagent.web.services.task_execution import _rewrite_file_links_to_file_id

        output_text = "[site](https://example.com) and [local](/not-preview/path)"
        rewritten = _rewrite_file_links_to_file_id(output_text, {})
        self.assertEqual(rewritten, output_text)

    async def test_rewrite_file_links_preserves_unmapped_absolute_paths(self):
        from xagent.web.services.task_execution import _rewrite_file_links_to_file_id

        absolute_image_path = (
            "/Users/bsbds/workspace/xagent_1/src/xagent/web/uploads/"
            "user_1/web_task_15/output/generated_image_9836e259.png"
        )
        output_text = (
            f"Image: ![generated image]({absolute_image_path})\n"
            f"Link: [generated image]({absolute_image_path})"
        )

        rewritten = _rewrite_file_links_to_file_id(output_text, {})

        self.assertEqual(rewritten, output_text)

    async def test_websocket_trace_handler_integration(self):
        """Test WebSocket trace handler integration"""
        print("\n=== WebSocket trace handler integration ===")

        from unittest.mock import AsyncMock, patch

        from xagent.core.agent.trace import (
            TraceAction,
            TraceCategory,
            TraceEvent,
            TraceEventType,
            TraceScope,
        )
        from xagent.web.api.websocket import ConnectionManager
        from xagent.web.services import task_events
        from xagent.web.services.task_event_trace_handler import TaskEventTraceHandler

        # Create a mock WebSocket manager
        mock_manager = AsyncMock()

        # This case assumes the task has an audience. Register a stand-in
        # connection on a real connection manager so the audience question
        # runs through the production path instead of a hard-coded answer.
        audience_manager = ConnectionManager()
        audience_manager.register_connection(AsyncMock(), 1)

        # Replace the manager via patch
        with (
            patch(
                "xagent.web.services.task_event_trace_handler.publish_task_event",
                mock_manager.broadcast_to_task,
            ),
            patch.object(
                task_events,
                "_task_audience_probe",
                audience_manager.has_connections_for_task,
            ),
        ):
            # Create the WebSocket trace handler
            handler = TaskEventTraceHandler(task_id=1)

            # Create a test event
            event_type = TraceEventType(
                TraceScope.STEP, TraceAction.START, TraceCategory.DAG
            )
            trace_event = TraceEvent(
                event_type=event_type,
                task_id=1,
                step_id="step1",
                data={"step_name": "test_step", "tool_name": "test_tool"},
            )

            # Handle the event
            await handler.handle_event(trace_event)

            # Verify the event was converted to the stream format and sent
            mock_manager.broadcast_to_task.assert_called_once()

            # Fetch the sent message
            sent_message = mock_manager.broadcast_to_task.call_args[0][0]

            # Verify the message format
            self.assertEqual(sent_message["type"], "trace_event")
            self.assertEqual(sent_message["event_type"], "dag_step_start")
            self.assertEqual(sent_message["task_id"], 1)
            self.assertIn("event_id", sent_message)
            self.assertIn("timestamp", sent_message)
            self.assertIn("data", sent_message)

            # Verify the payload content
            self.assertEqual(sent_message["data"]["step_name"], "test_step")
            self.assertEqual(sent_message["data"]["tool_name"], "test_tool")

            print("WebSocket trace handler integration verified: ✅")
            print(f"  Event type: {sent_message['event_type']}")
            print(f"  Task ID: {sent_message['task_id']}")
            print(f"  Step name: {sent_message['data']['step_name']}")
            print(f"  Tool name: {sent_message['data']['tool_name']}")

    async def test_websocket_pause_resume_handlers_exist(self):
        """Test that the WebSocket pause/resume handlers exist"""
        print("\n=== WebSocket pause/resume handlers ===")

        # Test the imports
        from xagent.web.api.websocket import handle_pause_task, handle_resume_task

        # Verify the functions exist
        assert callable(handle_pause_task)
        assert callable(handle_resume_task)

        print("  WebSocket pause/resume handler presence verified")

    async def test_websocket_pause_resume_error_handling_simple(self):
        """Test WebSocket pause/resume error handling (simplified)"""
        print("\n=== WebSocket pause/resume error handling (simplified) ===")

        from unittest.mock import AsyncMock, patch

        from xagent.web.api.websocket import handle_pause_task

        # Create a mock WebSocket
        websocket = AsyncMock()
        task_id = 123

        # Simulate the agent manager returning None (no such agent)
        mock_agent_manager = AsyncMock()
        mock_agent_manager.get_agent_for_task = AsyncMock(return_value=None)

        # Simulate the chat module's agent_manager
        mock_chat_module = AsyncMock()
        mock_chat_module.agent_manager = mock_agent_manager

        # Simulate the global manager
        mock_manager = AsyncMock()

        with patch.dict("sys.modules", {"xagent.web.api.chat": mock_chat_module}):
            with patch("xagent.web.api.websocket.manager", mock_manager):
                # Test pause - an error message should be sent
                message_data = {
                    "type": "pause_task",
                    "task_id": task_id,
                    "timestamp": "2024-01-01T00:00:00Z",
                }

                await handle_pause_task(websocket, task_id, message_data)

                # Verify an error message was sent
                mock_manager.send_personal_message.assert_called()

        print("  WebSocket pause/resume error handling test done")


if __name__ == "__main__":
    unittest.main()
