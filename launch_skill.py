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
from threading import Event
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

        core_restarted = Event()

        def _restart_after_core_ready(_message=None) -> None:
            """Recycle the standalone skill after OVOS Core is rebuilt.

            The standalone skill and OVOS Core are separate containers.  The
            skill can register while Core is still starting, and Core can
            restart without restarting this process.  A fresh skill process
            registers its Padatious models only after the rebuilt Core is
            ready, while also guaranteeing that local event handlers exist
            exactly once.  Docker's ``unless-stopped`` policy brings this
            process back immediately.
            """
            logger.info(
                "OVOS Core announced mycroft.ready; recycling AVAROS skill "
                "for a clean intent registration"
            )
            core_restarted.set()

        # In standalone mode AVAROS may start before ovos-core intent services,
        # and ovos-core may restart independently later.
        bus.on("mycroft.ready", _restart_after_core_ready)

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
        while not core_restarted.wait(timeout=1):
            pass

        logger.info("Exiting AVAROS skill so Docker can restart it")
        # MessageBusClient owns background threads that can keep Python alive
        # after main() returns.  The container is the lifecycle boundary here;
        # exit directly and let the configured restart policy create a clean
        # process against the now-ready Core.
        os._exit(75)
            
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
