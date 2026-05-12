#!/usr/bin/env python3
"""Launcher for the HulkuBot AI GUI — runs Flask server."""

from hulku_ai_gui.flask_app import start_app


def main():
    print("🚀 Starting HulkuBot AI GUI (Flask)...")
    start_app(host='0.0.0.0', port=5000)


if __name__ == '__main__':
    main()
