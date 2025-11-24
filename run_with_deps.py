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

# Fix Windows console encoding issues
if sys.platform == 'win32':
    try:
        # Try to set UTF-8 encoding for stdout/stderr
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        # If reconfiguration fails, we'll handle encoding errors in print statements
        pass


def safe_print(*args, **kwargs):
    """Print function that handles encoding errors gracefully."""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # Fallback: replace problematic characters with ASCII equivalents
        safe_args = []
        for arg in args:
            if isinstance(arg, str):
                # Replace common emojis with ASCII equivalents
                safe_str = arg.replace('📦', '[PKG]').replace('✅', '[OK]').replace('⚠️', '[WARN]')
                safe_str = safe_str.replace('❌', '[ERR]').replace('📋', '[INFO]').replace('🚀', '[RUN]')
                safe_str = safe_str.replace('🔄', '[RETRY]')
                safe_args.append(safe_str)
            else:
                safe_args.append(arg)
        print(*safe_args, **kwargs)


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
    safe_print(f"\n📦 Installing missing package: {package_name}")
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
            safe_print(f"✅ Successfully installed {package_name}")
            return True
        else:
            safe_print(f"⚠️  Warning: pip install returned error code {result.returncode}")
            if result.stderr:
                print(f"Error: {result.stderr[:200]}")
            return False
    except subprocess.TimeoutExpired:
        safe_print(f"❌ Timeout installing {package_name}")
        return False
    except Exception as e:
        safe_print(f"❌ Failed to install {package_name}: {e}")
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
    
    # Special case: "google" module needs both packages
    if module_name == 'google':
        # Return a list to indicate multiple packages needed
        return ['google-cloud-translate', 'google-cloud-vision']
    
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
        safe_print("📋 Installing dependencies from requirements.txt...")
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
                safe_print("✅ Dependencies check complete\n")
                return True
            else:
                safe_print("⚠️  Warning: Some packages from requirements.txt failed to install")
                return False
        except Exception as e:
            safe_print(f"⚠️  Warning: Error installing from requirements.txt: {e}")
            return False
    else:
        safe_print("⚠️  Warning: requirements.txt not found, skipping initial dependency installation")
        return False


def run_main_with_auto_install(max_retries=10):
    """Run main.py with automatic installation of missing packages."""
    script_path = os.path.join(os.getcwd(), "main.py")
    
    if not os.path.exists(script_path):
        safe_print(f"❌ Error: {script_path} not found")
        sys.exit(1)
    
    # First, try to install from requirements.txt
    check_and_install_requirements()
    
    retries = 0
    installed_packages = set()
    
    while retries < max_retries:
        try:
            # Try to actually run the script
            safe_print(f"🚀 Running {script_path}...\n")
            
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
                    safe_print(f"❌ Error: Could not extract module name from error")
                    safe_print(f"Error output:\n{stderr_text[:500]}")
                    sys.exit(return_code)
                
                # Check if we've already tried to install this
                if module_name in installed_packages:
                    safe_print(f"❌ Error: Failed to install {module_name} after retry")
                    safe_print(f"Error output:\n{stderr_text[:500]}")
                    sys.exit(1)
                
                # Map module name to package name
                package_name = map_module_to_package(module_name)
                
                # Handle case where multiple packages are needed (e.g., google)
                if isinstance(package_name, list):
                    all_installed = True
                    for pkg in package_name:
                        if not install_package(pkg):
                            all_installed = False
                    
                    if all_installed:
                        installed_packages.add(module_name)
                        retries += 1
                        safe_print(f"🔄 Retrying... (attempt {retries}/{max_retries})\n")
                        continue
                    else:
                        safe_print(f"❌ Error: Could not install required packages: {package_name}")
                        safe_print(f"Error output:\n{stderr_text[:500]}")
                        sys.exit(1)
                else:
                    # Install the package
                    if install_package(package_name):
                        installed_packages.add(module_name)
                        retries += 1
                        safe_print(f"🔄 Retrying... (attempt {retries}/{max_retries})\n")
                        continue
                    else:
                        # Try alternative package name
                        if package_name != module_name:
                            safe_print(f"🔄 Trying alternative package name: {module_name}")
                            if install_package(module_name):
                                installed_packages.add(module_name)
                                retries += 1
                                safe_print(f"🔄 Retrying... (attempt {retries}/{max_retries})\n")
                                continue
                        
                        safe_print(f"❌ Error: Could not install required package: {package_name}")
                        safe_print(f"Error output:\n{stderr_text[:500]}")
                        sys.exit(1)
            else:
                # Other error - print and exit with return code
                if stderr_text:
                    safe_print(f"\n❌ Error running main.py:")
                    safe_print(stderr_text)
                sys.exit(return_code)
        
        except KeyboardInterrupt:
            safe_print("\n\n⚠️  Interrupted by user")
            sys.exit(0)
            
        except Exception as e:
            # Unexpected error
            safe_print(f"❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    if retries >= max_retries:
        safe_print(f"❌ Error: Exceeded maximum retry attempts ({max_retries})")
        sys.exit(1)


if __name__ == "__main__":
    try:
        run_main_with_auto_install()
    except KeyboardInterrupt:
        safe_print("\n\n⚠️  Interrupted by user")
        sys.exit(0)

