#!/usr/bin/env python3
import os
import sys
import subprocess
from ament_index_python.packages import get_package_share_directory

def main():
    # 1. Get the path to your package's share directory
    # Replace 'nlp_node' with your actual package name defined in package.xml
    package_name = 'franka_ai_node' 
    
    try:
        share_dir = get_package_share_directory(package_name)
        
        # 2. Path to the Streamlit script
        # We will configure setup.py to put gui.py in the 'script' folder or root of share
        script_path = os.path.join(share_dir, 'scripts', 'gui.py')
        
        if not os.path.exists(script_path):
            print(f"Error: Streamlit script not found at {script_path}")
            return

        print(f"🚀 Launching Streamlit App from: {script_path}")
        
        # 3. Execute Streamlit
        # We use sys.executable to ensure we use the same python environment as ROS
        cmd = [sys.executable, "-m", "streamlit", "run", script_path]
        subprocess.run(cmd)
        
    except Exception as e:
        print(f"Failed to launch streamlit: {e}")

if __name__ == '__main__':
    main()