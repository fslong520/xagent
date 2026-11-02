#!/usr/bin/env python3

"""
A more comprehensive WebSocket message classification test.
"""

import asyncio
import json
from datetime import datetime

import websockets


async def comprehensive_test():
    """Comprehensive WebSocket message classification test"""
    uri = "ws://localhost:8000/ws/chat/1001"

    try:
        print(f"Connecting to WebSocket: {uri}")
        async with websockets.connect(uri) as websocket:
            # Send test messages of different kinds
            test_messages = [
                {
                    "type": "chat",
                    "message": "Please analyze the current sales data and generate a report",
                    "context": {},
                },
                {
                    "type": "chat",
                    "message": "Search for the latest AI technology trends",
                    "context": {},
                },
            ]

            for i, test_message in enumerate(test_messages):
                print(f"\n--- Test {i + 1}: {test_message['message'][:30]}... ---")
                await websocket.send(json.dumps(test_message))

                # Receive responses
                left_panel_messages = []
                right_panel_messages = []
                llm_messages = []

                start_time = datetime.now()
                timeout = 20  # 20 second timeout

                while (datetime.now() - start_time).seconds < timeout:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                        data = json.loads(message)

                        # Simulate the frontend classification logic
                        if data.get("type") == "dag_status_update":
                            has_tool_data = (
                                data.get("tool_execution")
                                or data.get("llm_interaction")
                                or data.get("agent_thinking")
                                or data.get("agent_action")
                                or data.get("agent_action_result")
                                or data.get("agent_observation")
                                or data.get("agent_observation_result")
                                or data.get("agent_final_answer")
                                or data.get("agent_final_answer_start")
                            )

                            has_step_data = (
                                data.get("step_start")
                                or data.get("step_update")
                                or data.get("step_end")
                            )

                            is_plan_event = (
                                (
                                    data.get("plan_completed") is not None
                                    or data.get("execution_started") is not None
                                    or data.get("execution_completed") is not None
                                    or data.get("steps_count") is not None
                                )
                                and not has_step_data
                                and not has_tool_data
                                and not data.get("iteration_start")
                                and not data.get("iteration_end")
                            )

                            if is_plan_event:
                                left_panel_messages.append(data.get("message", ""))
                                print(f"  [left] {data.get('message', '')}")
                            else:
                                right_panel_messages.append(data.get("message", ""))
                                print(f"  [right] {data.get('message', '')}")

                                # Record LLM interactions
                                if data.get("llm_interaction"):
                                    llm_messages.append(data.get("message", ""))
                                    llm_info = data["llm_interaction"]
                                    if llm_info.get("type") == "request":
                                        print(
                                            f"    -> LLM request: {llm_info.get('model', 'unknown')}"
                                        )
                                    elif llm_info.get("type") == "response":
                                        print(
                                            f"    -> LLM response: {llm_info.get('result_type', 'unknown')}"
                                        )

                        elif data.get("type") == "task_completed":
                            print(
                                f"  [done] Task completed: {data.get('result', '')[:50]}..."
                            )
                            break

                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        print(f"Error while handling a message: {e}")
                        continue

                # Print the statistics for this test
                print(f"  Test {i + 1} results:")
                print(f"    Left panel messages: {len(left_panel_messages)}")
                print(f"    Right panel messages: {len(right_panel_messages)}")
                print(f"    LLM interaction messages: {len(llm_messages)}")

                # Check for duplicates
                duplicates = set(left_panel_messages) & set(right_panel_messages)
                if duplicates:
                    print(f"    ❌ Duplicate messages found: {duplicates}")
                else:
                    print("    ✅ No duplicate messages")

                # Wait a moment before the next test
                await asyncio.sleep(2)

            print(f"\n{'=' * 50}")
            print("Comprehensive test complete!")

    except Exception as e:
        print(f"Test failed: {e}")


if __name__ == "__main__":
    asyncio.run(comprehensive_test())
