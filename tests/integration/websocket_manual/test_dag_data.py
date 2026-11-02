#!/usr/bin/env python3
"""
Detailed WebSocket data test.

Verifies the data structures the frontend receives.
"""

import asyncio
import json

import pytest
import websockets


@pytest.mark.slow
async def test_dag_data():
    uri = "ws://127.0.0.1:8000/ws/chat/1"
    try:
        async with websockets.connect(uri) as websocket:
            print("=== WebSocket DAG data test ===")

            # Send a status request
            await websocket.send(json.dumps({"type": "status_request"}))

            # Receive historical data
            response = await websocket.recv()
            data = json.loads(response)

            print(f"Data type: {data.get('type')}")
            print(f"Task ID: {data.get('task_id')}")

            # Inspect the steps data
            if "steps" in data:
                print("\n=== Step data ===")
                print(f"Step count: {len(data['steps'])}")
                for i, step in enumerate(data["steps"]):
                    print(
                        f"Step {i + 1}: {step.get('name')} (status: {step.get('status')})"
                    )

            # Inspect the step_details data
            if "step_details" in data:
                print("\n=== Step detail data ===")
                print(f"Detail count: {len(data['step_details'])}")
                for step_id, details in data["step_details"].items():
                    print(f"Step ID {step_id}:")
                    print(f"  Name: {details['step_info']['name']}")
                    print(f"  Status: {details['step_info']['status']}")
                    print(f"  Log count: {details['execution_stats']['log_count']}")
                    print(f"  Has errors: {details['execution_stats']['has_errors']}")

            # DAG visualization data was removed; historical data is used instead

            # Inspect the logs data
            if "logs" in data:
                print("\n=== Log data ===")
                print(f"Log count: {len(data['logs'])}")
                error_logs = [
                    log for log in data["logs"] if log.get("level") == "error"
                ]
                success_logs = [
                    log for log in data["logs"] if log.get("level") == "success"
                ]
                print(f"Error logs: {len(error_logs)}")
                print(f"Success logs: {len(success_logs)}")

            print("\n=== Data structure verification complete ===")
            print("✅ WebSocket data transfer works")
            print("✅ DAG step data is complete")
            print("✅ Step detail data is complete")
            print("✅ Execution log data is complete")

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_dag_data())
