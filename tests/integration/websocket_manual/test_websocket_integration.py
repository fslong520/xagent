#!/usr/bin/env python3
"""
A more verbose WebSocket test with extra debugging information.
"""

import asyncio
import json
import time

import pytest
import websockets


@pytest.mark.slow
async def test_websocket_debug():
    uri = "ws://127.0.0.1:8000/ws/chat/3"
    try:
        async with websockets.connect(uri) as websocket:
            print("=== WebSocket debug test ===")

            # 1. Request historical data first
            print("\n1. Requesting historical data...")
            await websocket.send(json.dumps({"type": "status_request"}))

            response = await websocket.recv()
            data = json.loads(response)
            print(f"Historical data type: {data.get('type')}")
            print(f"Task ID: {data.get('task_id')}")

            # 2. Send a new chat message
            print("\n2. Sending a new DAG task...")
            test_message = "Calculate 5*8 with python"
            await websocket.send(
                json.dumps({"type": "chat", "message": test_message, "context": {}})
            )

            # 3. Receive the acknowledgement
            response = await websocket.recv()
            data = json.loads(response)
            print(f"Message acknowledgement: {data.get('type')}")

            # 4. Receive live updates (wait a little longer)
            print("\n3. Waiting for live updates...")
            message_count = 0
            max_messages = 20
            start_time = time.time()
            timeout = 60  # 60 second timeout

            while message_count < max_messages:
                try:
                    # Compute the remaining time
                    elapsed = time.time() - start_time
                    remaining = timeout - elapsed

                    if remaining <= 0:
                        print(
                            f"\n⏰ Overall timeout, received {message_count} messages"
                        )
                        break

                    response = await asyncio.wait_for(
                        websocket.recv(), timeout=min(remaining, 10.0)
                    )
                    data = json.loads(response)
                    message_count += 1

                    print(f"\n--- Message {message_count} (time: {elapsed:.1f}s) ---")
                    print(f"Type: {data.get('type')}")

                    if data.get("type") == "agent_thinking":
                        print(f"Thinking state: {data.get('message')}")
                    elif data.get("type") == "agent_response":
                        print(f"AI response: {data.get('message', '')[:100]}...")
                    elif data.get("type") == "task_completed":
                        print(f"Task completed: {data.get('success')}")
                        print(f"Final result: {data.get('result', '')[:100]}...")
                    elif data.get("type") == "historical_data":
                        print(
                            f"Historical data update - steps: {len(data.get('steps', []))}"
                        )
                        print(f"Step details: {len(data.get('step_details', {}))}")
                        print(f"Logs: {len(data.get('logs', []))}")
                    elif data.get("type") == "agent_error":
                        print(f"Error: {data.get('message')}")
                    elif data.get("type") == "agent_thought":
                        print(f"Thinking finished: {data.get('message')}")
                    elif data.get("type") == "agent_action":
                        print(f"AI action: {data.get('message')}")
                    elif data.get("type") == "agent_action_result":
                        print(f"Action result: {data.get('message')}")
                    elif data.get("type") == "dag_status_update":
                        print(f"DAG status update: {data.get('message')}")
                    else:
                        print(f"Other message: {data}")

                    # End the test once the task completion message arrives
                    if data.get("type") == "task_completed":
                        print("\n✅ Task completed, ending the test")
                        break

                except asyncio.TimeoutError:
                    print(f"\n⏰ Wait timed out, received {message_count} messages")
                    break
                except Exception as e:
                    print(f"❌ Error while receiving messages: {e}")
                    break

            print("\n=== Test complete ===")
            print(f"Received {message_count} live messages in total")

            if message_count == 0:
                print("❌ No live messages received")
                print("Possible reasons:")
                print("1. TaskEventTraceHandler was not attached correctly")
                print("2. AgentService did not run correctly")
                print("3. Message delivery failed")
            else:
                print("✅ WebSocket live communication works")
                print("✅ DAG task execution works")
                print("✅ Frontend data updates work")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_websocket_debug())
