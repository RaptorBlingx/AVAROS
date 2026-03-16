#!/usr/bin/env python3
"""
AVAROS Skill Launcher

This script properly initializes and runs the AVAROS skill,
connecting it to the OVOS messagebus for intent handling.
"""

import sys
import os
import logging
import time
from threading import Lock
from pathlib import Path

# Ensure skill package is importable when running as standalone script
# The Dockerfile sets WORKDIR=/opt/avaros, making 'skill' a package
skill_dir = Path(__file__).parent / "skill"
sys.path.insert(0, str(skill_dir.parent))

from skill import AVAROSSkill
from ovos_bus_client.client import MessageBusClient
from ovos_bus_client.message import Message

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("AVAROS")


def main() -> None:
    """Main entry point for AVAROS skill."""
    logger.info("Starting AVAROS skill...")
    
    try:
        # Create MessageBus client connection
        # In WASABI OVOS, the messagebus is accessible at ovos_messagebus:8181
        logger.info("Connecting to OVOS messagebus...")
        bus_host = os.environ.get("MESSAGEBUS_HOST", "ovos_messagebus")
        bus = MessageBusClient(host=bus_host, port=8181)
        bus.run_in_thread()
        
        # Create skill instance with skill_id and bus
        # The skill_id must be unique and follow OVOS conventions
        logger.info("Creating and initializing AVAROS skill...")
        skill = AVAROSSkill(skill_id="avaros-manufacturing.avaros", bus=bus)

        register_lock = Lock()
        last_reregister_monotonic = 0.0
        reregister_cooldown_sec = 30.0

        def _register_intents_when_core_ready(_message=None) -> None:
            """Re-register intents after OVOS announces system-ready."""
            nonlocal last_reregister_monotonic
            now = time.monotonic()
            if now - last_reregister_monotonic < reregister_cooldown_sec:
                return
            with register_lock:
                now = time.monotonic()
                if now - last_reregister_monotonic < reregister_cooldown_sec:
                    return
                try:
                    registered_now = skill._register_intent_handlers()
                    if registered_now > 0:
                        bus.emit(Message("padatious:train"))
                        logger.info(
                            "Re-registered %d AVAROS intents after mycroft.ready",
                            registered_now,
                        )
                    else:
                        logger.info(
                            "AVAROS intent registrations already up to date after mycroft.ready",
                        )
                    last_reregister_monotonic = now
                except Exception as exc:
                    logger.warning(
                        "Intent re-registration after mycroft.ready failed: %s",
                        exc,
                    )

        # In standalone mode AVAROS may start before ovos-core intent services,
        # and ovos-core may restart independently later.
        bus.on("mycroft.ready", _register_intents_when_core_ready)

        # In standalone mode (outside OVOS SkillManager), initialize()
        # is not guaranteed to be called automatically.
        skill.initialize()
        bus.emit(Message("padatious:train"))
        
        # Wait briefly for async bus wiring to settle
        time.sleep(2)
        
        logger.info("AVAROS skill initialized successfully!")
        logger.info("Intents registered and listening on messagebus...")
        
        # Keep the skill running
        # The skill's bus client will handle events in the background
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("AVAROS skill shutting down...")
        if 'bus' in locals():
            bus.close()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Failed to start AVAROS skill: {e}", exc_info=True)
        if 'bus' in locals():
            bus.close()
        sys.exit(1)


if __name__ == "__main__":
    main()
