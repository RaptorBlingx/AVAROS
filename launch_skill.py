#!/usr/bin/env python3
"""
AVAROS Skill Launcher

This script properly initializes and runs the AVAROS skill,
connecting it to the OVOS messagebus for intent handling.
"""

import sys
import logging
import time
from pathlib import Path

# Ensure skill package is importable when running as standalone script
# The Dockerfile sets WORKDIR=/opt/avaros, making 'skill' a package
skill_dir = Path(__file__).parent / "skill"
sys.path.insert(0, str(skill_dir.parent))

from skill import AVAROSSkill
from ovos_bus_client.client import MessageBusClient

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
        bus = MessageBusClient(host="ovos_messagebus", port=8181)
        bus.run_in_thread()
        
        # Create skill instance with skill_id and bus
        # The skill_id must be unique and follow OVOS conventions
        logger.info("Creating and initializing AVAROS skill...")
        skill = AVAROSSkill(skill_id="avaros-manufacturing.avaros", bus=bus)
        
        # Wait for skill initialization to complete
        # OVOSSkill.initialize() is called automatically during construction
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
