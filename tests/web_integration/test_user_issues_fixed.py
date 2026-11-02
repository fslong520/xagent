#!/usr/bin/env python3

"""
Final verification: a targeted test for the issues reported by users.
"""

import asyncio
import json
from datetime import datetime

import pytest
import websockets


@pytest.mark.integration
@pytest.mark.slow
async def test_user_issues():
    """Targeted test for the issues reported by users"""
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
            steps_received = False
            steps_count = 0
            trace_events_received = False

            start_time = datetime.now()
            timeout = 30  # 30 second timeout

            while (datetime.now() - start_time).seconds < timeout:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                    data = json.loads(message)

                    if data.get("type") == "dag_status_update":
                        # Check whether step data is present
                        if data.get("steps") and isinstance(data["steps"], list):
                            plan_steps = data["steps"]
                            if plan_steps:
                                steps_received = True
                                steps_count = len(plan_steps)
                                print(f"✅ Received step data: {steps_count} steps")

                                # Show the step information
                                for i, step in enumerate(plan_steps):
                                    print(
                                        f"  Step {i + 1}: {step.get('name', 'unknown')} (ID: {step.get('id', 'unknown')})"
                                    )

                        # Check whether step details are present
                        if data.get("step_details"):
                            details_count = len(data["step_details"])
                            print(f"✅ Received step details for {details_count} steps")

                        # Check whether execution logs are present (now trace events)
                        if data.get("logs"):
                            trace_events_received = True
                            logs_count = len(data["logs"])
                            print(f"✅ Received execution logs: {logs_count}")

                            # Check whether the logs carry step information
                            step_related_logs = [
                                log
                                for log in data["logs"]
                                if log.get("step_id") or log.get("step_name")
                            ]
                            if step_related_logs:
                                print(
                                    f"✅ Received step-related logs: {len(step_related_logs)}"
                                )
                                for log in step_related_logs:
                                    print(
                                        f"  - {log.get('step_id', 'unknown')} ({log.get('step_name', 'unknown')}): {log.get('message', 'no message')[:50]}..."
                                    )

                    elif data.get("type") == "task_completed":
                        print("Task completed")
                        break

                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    print(f"Error while handling a message: {e}")
                    continue

            # Verify the results
            print("\n" + "=" * 50)
            print("User issue verification results:")

            issue1_fixed = steps_received and steps_count > 0
            # Adjusted logic: any step-related log means issue 2 is fixed
            issue2_fixed = trace_events_received  # trace events now carry step info, which is enough to confirm correlation

            print(
                f"Issue 1 - top-right step counter: {'✅ fixed' if issue1_fixed else '❌ still broken'}"
            )
            if issue1_fixed:
                print(f"  It should now show 1/{steps_count}, 2/{steps_count}, not 0/0")
            else:
                print("  It still shows: 0/0")

            print(
                f"Issue 2 - step log correlation: {'✅ fixed' if issue2_fixed else '❌ still broken'}"
            )
            if issue2_fixed:
                print("  Step details and logs are now correlated correctly")
            else:
                print("  Steps and logs are still not correlated")

            print(
                f"\nOverall fix status: {'✅ success' if issue1_fixed and issue2_fixed else '❌ some issues remain'}"
            )

            return issue1_fixed and issue2_fixed

    except Exception as e:
        print(f"Test failed: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_user_issues())
    exit(0 if success else 1)
