#!/usr/bin/env python3
"""
Wrapper script to run main.py with automatic dependency installation.
This script will install missing libraries automatically if needed.
"""

import sys
import subprocess
import re
import os
import importlib

# Module to package name mappings
MODULE_TO_PACKAGE = {
    'cv2': 'opencv-python',
    'PIL': 'pillow',
    'PyQt5': 'PyQt5',
    'skimage': 'scikit-image',
    'google.cloud.vision': 'google-cloud-vision',
    'google.cloud.translate': 'google-cloud-translate',
    'pytesseract': 'pytesseract',
    'paddleocr': 'paddleocr',
    'paddle': 'paddlepaddle',
    'numpy': 'numpy',
    'pyautogui': 'pyautogui',
}


def install_package(package_name, quiet=True):
    """Install a package using pip."""
    print(f"\n📦 Installing missing package: {package_name}")
    try:
        cmd = [sys.executable, "-m", "pip", "install"]
        if quiet:
            cmd.append("-q")
        cmd.append(package_name)
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode == 0:
            print(f"✅ Successfully installed {package_name}")
            return True
        else:
            print(f"⚠️  Warning: pip install returned error code {result.returncode}")
            if result.stderr:
                print(f"Error: {result.stderr[:200]}")
            return False
    except subprocess.TimeoutExpired:
        print(f"❌ Timeout installing {package_name}")
        return False
    except Exception as e:
        print(f"❌ Failed to install {package_name}: {e}")
        return False


def extract_module_name(error_msg):
    """Extract module name from ModuleNotFoundError message."""
    # Pattern: "No module named 'module_name'"
    match = re.search(r"No module named ['\"]([^'\"]+)['\"]", error_msg)
    if match:
        return match.group(1)
    
    # Pattern: "No module named module_name" (without quotes)
    match = re.search(r"No module named (\S+)", error_msg)
    if match:
        return match.group(1)
    
    return None


def map_module_to_package(module_name):
    """Map Python module name to pip package name."""
    # Check exact match first
    if module_name in MODULE_TO_PACKAGE:
        return MODULE_TO_PACKAGE[module_name]
    
    # Check if it starts with a known prefix
    for key, value in MODULE_TO_PACKAGE.items():
        if module_name.startswith(key):
            return value
    
    # For dotted modules, try the first part
    first_part = module_name.split('.')[0]
    if first_part in MODULE_TO_PACKAGE:
        return MODULE_TO_PACKAGE[first_part]
    
    # Special cases for common dotted imports
    if module_name.startswith('google.cloud'):
        if 'translate' in module_name:
            return 'google-cloud-translate'
        else:
            return 'google-cloud-vision'
    
    # Default: try the module name itself, replacing underscores with hyphens
    return module_name.replace('_', '-')


def check_and_install_requirements():
    """Check if requirements.txt exists and install from it."""
    requirements_file = os.path.join(os.getcwd(), "requirements.txt")
    
    if os.path.exists(requirements_file):
        print("📋 Installing dependencies from requirements.txt...")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "--upgrade", "pip"],
                capture_output=True,
                timeout=60
            )
            
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "-r", requirements_file],
                capture_output=True,
                timeout=600  # 10 minute timeout for requirements.txt
            )
            
            if result.returncode == 0:
                print("✅ Dependencies check complete\n")
                return True
            else:
                print("⚠️  Warning: Some packages from requirements.txt failed to install")
                return False
        except Exception as e:
            print(f"⚠️  Warning: Error installing from requirements.txt: {e}")
            return False
    else:
        print("⚠️  Warning: requirements.txt not found, skipping initial dependency installation")
        return False


def run_main_with_auto_install(max_retries=10):
    """Run main.py with automatic installation of missing packages."""
    script_path = os.path.join(os.getcwd(), "main.py")
    
    if not os.path.exists(script_path):
        print(f"❌ Error: {script_path} not found")
        sys.exit(1)
    
    # First, try to install from requirements.txt
    check_and_install_requirements()
    
    retries = 0
    installed_packages = set()
    
    while retries < max_retries:
        try:
            # Try to actually run the script
            print(f"🚀 Running {script_path}...\n")
            
            # Run as subprocess to capture stderr
            process = subprocess.Popen(
                [sys.executable, script_path],
                stdout=sys.stdout,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=os.getcwd()
            )
            
            # Capture stderr in real-time
            stderr_lines = []
            while True:
                output = process.stderr.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    stderr_lines.append(output)
                    # Print stderr to console in real-time
                    sys.stderr.write(output)
                    sys.stderr.flush()
            
            # Wait for process to complete
            return_code = process.wait()
            
            # If successful, exit with the same code
            if return_code == 0:
                sys.exit(0)
            
            # Check stderr for import errors
            stderr_text = ''.join(stderr_lines)
            
            if "ModuleNotFoundError" in stderr_text or "No module named" in stderr_text:
                module_name = extract_module_name(stderr_text)
                
                if not module_name:
                    print(f"❌ Error: Could not extract module name from error")
                    print(f"Error output:\n{stderr_text[:500]}")
                    sys.exit(return_code)
                
                # Check if we've already tried to install this
                if module_name in installed_packages:
                    print(f"❌ Error: Failed to install {module_name} after retry")
                    print(f"Error output:\n{stderr_text[:500]}")
                    sys.exit(1)
                
                # Map module name to package name
                package_name = map_module_to_package(module_name)
                
                # Install the package
                if install_package(package_name):
                    installed_packages.add(module_name)
                    retries += 1
                    print(f"🔄 Retrying... (attempt {retries}/{max_retries})\n")
                    continue
                else:
                    # Try alternative package name
                    if package_name != module_name:
                        print(f"🔄 Trying alternative package name: {module_name}")
                        if install_package(module_name):
                            installed_packages.add(module_name)
                            retries += 1
                            print(f"🔄 Retrying... (attempt {retries}/{max_retries})\n")
                            continue
                    
                    print(f"❌ Error: Could not install required package: {package_name}")
                    print(f"Error output:\n{stderr_text[:500]}")
                    sys.exit(1)
            else:
                # Other error - print and exit with return code
                if stderr_text:
                    print(f"\n❌ Error running main.py:")
                    print(stderr_text)
                sys.exit(return_code)
        
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            sys.exit(0)
            
        except Exception as e:
            # Unexpected error
            print(f"❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    if retries >= max_retries:
        print(f"❌ Error: Exceeded maximum retry attempts ({max_retries})")
        sys.exit(1)


if __name__ == "__main__":
    try:
        run_main_with_auto_install()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(0)

