#!/usr/bin/env python3

"""
Test the fix for step_id in historical data.
"""

import asyncio
import json
from datetime import datetime

import pytest
import websockets


@pytest.mark.integration
@pytest.mark.slow
async def test_historical_step_id_fix():
    """Test the fix for step_id in historical data"""
    uri = "ws://localhost:8000/ws/chat/1001"

    try:
        print(f"Connecting to WebSocket: {uri}")
        async with websockets.connect(uri) as websocket:
            # Send a test message
            test_message = {
                "type": "chat",
                "message": "2 * 3 = ?",
                "context": {},
            }

            print(f"Sending test message: {test_message['message']}")
            await websocket.send(json.dumps(test_message))

            # Receive responses
            step_id_found = False
            step_events_with_id = []

            start_time = datetime.now()
            timeout = 30  # 30 second timeout

            while (datetime.now() - start_time).seconds < timeout:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                    data = json.loads(message)

                    if data.get("type") == "trace_event":
                        # Check whether step_id is present
                        if data.get("step_id"):
                            step_id_found = True
                            step_events_with_id.append(
                                {
                                    "event_type": data.get("event_type"),
                                    "step_id": data.get("step_id"),
                                    "has_step_name": "step_name"
                                    in data.get("data", {}),
                                }
                            )
                            print(
                                f"✅ Found an event carrying step_id: {data.get('event_type')} (step_id: {data.get('step_id')})"
                            )

                        # Check the dag_step_start event specifically
                        if data.get("event_type") == "dag_step_start":
                            if data.get("step_id"):
                                print(
                                    f"✅ dag_step_start event carries step_id: {data.get('step_id')}"
                                )
                            else:
                                print("❌ dag_step_start event is missing step_id")

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
            print("Historical data step_id fix verification results:")

            print(f"Events carrying step_id: {len(step_events_with_id)}")
            for event in step_events_with_id:
                print(
                    f"  - {event['event_type']}: step_id={event['step_id']}, step_name={event['has_step_name']}"
                )

            if step_id_found:
                print("✅ Historical data step_id fix works")
                return True
            else:
                print("❌ Historical data still has no step_id")
                return False

    except Exception as e:
        print(f"Test failed: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_historical_step_id_fix())
    exit(0 if success else 1)
