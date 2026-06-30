"""Standalone entry point for PyInstaller build.

Launches the CAYE Watermark WebUI directly.
"""
from caye_watermark.webui import launch_app

if __name__ == "__main__":
    launch_app()
