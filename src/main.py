#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Main entry point for deSEC Qt DNS Manager.
Sets up the application, initializes components, and launches the UI.
"""

import sys
import os
import logging
from PySide6 import QtGui, QtCore, QtWidgets

# Import local modules
from profile_manager import ProfileManager
from api_client import APIClient
from main_window import MainWindow

# Set up logging
LOG_DIR = os.path.expanduser("~/.config/desecqt/logs")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR, exist_ok=True)
    
LOG_FILE = os.path.join(LOG_DIR, "desecqt.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Main application entry point."""
    try:
        # Create Qt application
        app = QtWidgets.QApplication(sys.argv)
        app.setApplicationName("deSEC Qt DNS Manager")
        app.setOrganizationName("deSECQT")
        app.setWindowIcon(QtGui.QIcon("icon.png"))  # Add an icon if available

        # Force application to process events before theme detection
        app.processEvents()

        # Set up profile management
        profile_manager = ProfileManager()
        config_manager = profile_manager.get_config_manager()
        cache_manager = profile_manager.get_cache_manager()
        api_client = APIClient(config_manager)

        # Create and show main window
        main_window = MainWindow(config_manager, api_client, cache_manager, profile_manager)
        main_window.show()

        # Launch the application
        logger.info("Application started")
        sys.exit(app.exec())
        
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        # Show an error dialog if GUI is available
        try:
            QtWidgets.QMessageBox.critical(None, "Fatal Error", 
                f"The application encountered a fatal error and needs to close.\n\nDetails: {str(e)}")
        except Exception:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()
