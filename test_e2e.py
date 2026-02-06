#!/usr/bin/env python3
"""
End-to-End Test Script for AVAROS Skill

Tests the full intent recognition → skill execution → response pipeline
via OVOS message bus. This simulates what would happen with real voice input.
"""

import sys
import time
from datetime import datetime

try:
    from ovos_bus_client import MessageBusClient, Message
except ImportError:
    from mycroft_bus_client import MessageBusClient, Message

# Test configuration
MESSAGEBUS_HOST = "ovos_messagebus"
MESSAGEBUS_PORT = 8181
TEST_TIMEOUT = 10  # seconds


class E2ETestRunner:
    """End-to-end test runner for AVAROS skill."""
    
    def __init__(self):
        self.client = None
        self.response_received = False
        self.response_data = None
        self.start_time = None
        self.end_time = None
        
    def connect(self):
        """Connect to OVOS message bus."""
        print(f"Connecting to message bus at {MESSAGEBUS_HOST}:{MESSAGEBUS_PORT}")
        self.client = MessageBusClient(host=MESSAGEBUS_HOST, port=MESSAGEBUS_PORT)
        self.client.run_in_thread()
        time.sleep(2)  # Allow connection to establish
        print("✓ Connected to message bus")
        
    def on_speak(self, message):
        """Handle speak messages from skill."""
        self.response_received = True
        self.end_time = time.time()
        self.response_data = message.data
        print(f"✓ Response received: {message.data.get('utterance', 'No utterance')}")
        
    def test_intent(self, utterance: str, intent_name: str) -> dict:
        """
        Test a single intent.
        
        Args:
            utterance: The text to send (simulates what user says)
            intent_name: Expected intent name for validation
            
        Returns:
            dict with test results
        """
        print(f"\n{'='*60}")
        print(f"Testing: {utterance}")
        print(f"Expected Intent: {intent_name}")
        print(f"{'='*60}")
        
        # Reset state
        self.response_received = False
        self.response_data = None
        self.start_time = time.time()
        self.end_time = None
        
        # Subscribe to speak messages
        self.client.on("speak", self.on_speak)
        
        # Send utterance (this triggers intent matching)
        message = Message(
            "recognizer_loop:utterance",
            data={"utterances": [utterance], "lang": "en-us"}
        )
        self.client.emit(message)
        
        # Wait for response
        timeout_time = self.start_time + TEST_TIMEOUT
        while time.time() < timeout_time:
            if self.response_received:
                break
            time.sleep(0.1)
        
        # Calculate roundtrip time
        roundtrip_time = (self.end_time - self.start_time) if self.end_time else TEST_TIMEOUT
        
        # Build result
        result = {
            "utterance": utterance,
            "intent": intent_name,
            "success": self.response_received,
            "roundtrip_ms": int(roundtrip_time * 1000),
            "response": self.response_data.get("utterance", "No response") if self.response_data else "TIMEOUT",
            "timestamp": datetime.now().isoformat()
        }
        
        # Print result
        status = "✓ PASS" if result["success"] else "✗ FAIL"
        print(f"\nResult: {status}")
        print(f"Response: {result['response']}")
        print(f"Roundtrip: {result['roundtrip_ms']}ms")
        
        if not result["success"]:
            print("⚠ WARNING: Response timeout or no response received")
        elif result['roundtrip_ms'] > 10000:
            print(f"⚠ WARNING: Roundtrip time exceeds 10s target ({result['roundtrip_ms']}ms)")
        
        return result
        
    def disconnect(self):
        """Disconnect from message bus."""
        if self.client:
            self.client.close()
            print("\n✓ Disconnected from message bus")


def main():
    """Run end-to-end tests."""
    print("="*60)
    print("AVAROS End-to-End Test Suite")
    print("="*60)
    print(f"Start Time: {datetime.now().isoformat()}")
    print()
    
    # Define test cases (minimum 3 required)
    test_cases = [
        {
            "utterance": "What's the energy per unit for Line-1?",
            "intent": "kpi.energy.per_unit"
        },
        {
            "utterance": "What's the OEE for Line-2?",
            "intent": "kpi.oee"
        },
        {
            "utterance": "What's the scrap rate?",
            "intent": "kpi.scrap_rate"
        },
    ]
    
    # Run tests
    runner = E2ETestRunner()
    results = []
    
    try:
        runner.connect()
        
        for test_case in test_cases:
            result = runner.test_intent(
                utterance=test_case["utterance"],
                intent_name=test_case["intent"]
            )
            results.append(result)
            time.sleep(2)  # Brief pause between tests
            
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        return 1
    except Exception as e:
        print(f"\n\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        runner.disconnect()
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for r in results if r["success"])
    failed = len(results) - passed
    avg_roundtrip = sum(r["roundtrip_ms"] for r in results) / len(results) if results else 0
    max_roundtrip = max(r["roundtrip_ms"] for r in results) if results else 0
    
    print(f"Total Tests: {len(results)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Average Roundtrip: {avg_roundtrip:.0f}ms")
    print(f"Max Roundtrip: {max_roundtrip}ms")
    print()
    
    # Print detailed results table
    print("\nDetailed Results:")
    print("-" * 60)
    print(f"{'Intent':<25} {'Status':<10} {'Time (ms)':<12}")
    print("-" * 60)
    for r in results:
        status = "PASS" if r["success"] else "FAIL"
        print(f"{r['intent']:<25} {status:<10} {r['roundtrip_ms']:<12}")
    print("-" * 60)
    
    # Check acceptance criteria
    print("\nAcceptance Criteria:")
    print(f"  [{'✓' if passed >= 3 else '✗'}] 3+ intents produce responses: {passed}/3")
    print(f"  [{'✓' if max_roundtrip < 10000 else '✗'}] Roundtrip < 10s: {max_roundtrip}ms < 10000ms")
    print(f"  [{'✓' if failed == 0 else '✗'}] No unhandled exceptions: {failed} failures")
    
    # Exit code
    if passed >= 3 and max_roundtrip < 10000 and failed == 0:
        print("\n✓ ALL TESTS PASSED")
        return 0
    else:
        print("\n✗ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
