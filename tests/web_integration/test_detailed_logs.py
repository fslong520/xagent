#!/usr/bin/env python3

"""
Detailed test of log data reception and correlation.
"""

import asyncio
import json
from datetime import datetime

import pytest
import websockets


@pytest.mark.integration
@pytest.mark.slow
async def test_detailed_logs():
    """Detailed test of log data reception and correlation"""
    uri = "ws://localhost:8000/ws/chat/1001"

    try:
        print(f"Connecting to WebSocket: {uri}")
        async with websockets.connect(uri) as websocket:
            # Send a test message
            test_message = {
                "type": "chat",
                "message": "Analyze the sales data and generate a report",
                "context": {},
            }

            print(f"Sending test message: {test_message['message']}")
            await websocket.send(json.dumps(test_message))

            # Receive responses
            message_count = 0
            all_logs = []
            step_logs = []
            steps_with_log_data = {}

            start_time = datetime.now()
            timeout = 60  # 60 second timeout

            while (datetime.now() - start_time).seconds < timeout:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    data = json.loads(message)
                    message_count += 1

                    if data.get("type") == "dag_status_update":
                        # Inspect the log data
                        if "logs" in data:
                            logs = data["logs"]
                            print(
                                f"\n--- Message {message_count}: received {len(logs)} logs ---"
                            )

                            for i, log in enumerate(logs):
                                print(f"  Log {i + 1}:")
                                print(f"    Level: {log.get('level', 'unknown')}")
                                print(
                                    f"    Message: {log.get('message', 'no message')[:100]}..."
                                )
                                print(f"    Step ID: {log.get('step_id', 'None')}")
                                print(f"    Step name: {log.get('step_name', 'None')}")
                                print(f"    Timestamp: {log.get('timestamp', 'None')}")

                                # Add to the log list
                                all_logs.append(log)

                                # If step information is present, add it to the step logs
                                if log.get("step_id") or log.get("step_name"):
                                    step_logs.append(log)
                                    step_id = log.get(
                                        "step_id", log.get("step_name", "unknown")
                                    )
                                    if step_id not in steps_with_log_data:
                                        steps_with_log_data[step_id] = []
                                    steps_with_log_data[step_id].append(log)

                    elif data.get("type") == "task_completed":
                        print("\n--- Task completed ---")
                        break

                except asyncio.TimeoutError:
                    print("Timed out waiting for a message, continuing...")
                    continue
                except Exception as e:
                    print(f"Error while handling a message: {e}")
                    continue

            # Analyze the results
            print("\n" + "=" * 60)
            print("Detailed log analysis results:")
            print(f"Total messages: {message_count}")
            print(f"Total logs: {len(all_logs)}")
            print(f"Step-related logs: {len(step_logs)}")
            print(f"Steps with log data: {len(steps_with_log_data)}")

            if steps_with_log_data:
                print("\nStep log correlation details:")
                for step_id, logs in steps_with_log_data.items():
                    print(f"  Step {step_id}: {len(logs)} logs")
                    for log in logs:
                        print(
                            f"    - {log.get('level', 'unknown')}: {log.get('message', 'no message')[:60]}..."
                        )

            # Test the frontend log correlation logic
            print("\n" + "=" * 60)
            print("Simulating the frontend log correlation logic:")

            # Simulated step data
            mock_steps = [
                {"id": "step1", "name": "Research Sales Analysis Methods"},
                {"id": "step2", "name": "Find Sample Sales Data"},
                {"id": "step3", "name": "Set Up Analysis Environment"},
                {"id": "step4", "name": "Collect and Load Data"},
                {"id": "step5", "name": "Data Cleaning and Preparation"},
            ]

            for step in mock_steps:
                # Simulate the frontend's log filtering logic
                step_related_logs = []

                for log in all_logs:
                    # Check the structured step information
                    if log.get("step_id") == step["id"]:
                        step_related_logs.append(log)
                    # Check for a step name match
                    elif log.get("step_name") == step["name"]:
                        step_related_logs.append(log)
                    # Fall back to filtering on the message content
                    elif log.get("message"):
                        message = log["message"].lower()
                        step_name = step["name"].lower()

                        if (
                            step_name in message
                            or step["id"] in message
                            or any(
                                keyword in message
                                for keyword in [
                                    "research",
                                    "analysis",
                                    "data",
                                    "cleaning",
                                ]
                            )
                        ):
                            step_related_logs.append(log)

                print(f"Step {step['id']} ({step['name']}):")
                print(f"  Related logs: {len(step_related_logs)}")
                if step_related_logs:
                    for log in step_related_logs[:2]:  # show only the first 2
                        print(f"    - {log.get('message', 'no message')[:80]}...")
                else:
                    print("    ❌ No related logs")

            return len(step_logs) > 0

    except Exception as e:
        print(f"Test failed: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_detailed_logs())
    exit(0 if success else 1)
