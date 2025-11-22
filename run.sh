#!/bin/bash

# Script to run main.py with automatic dependency installation
# This script will install missing libraries automatically if needed

set -e  # Exit on error (but we'll handle errors manually)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo -e "${GREEN}Starting Dainn Screen Translator...${NC}"

# Check if Python is installed
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo -e "${RED}Error: Python is not installed or not in PATH${NC}"
    exit 1
fi

# Determine Python command
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo -e "${RED}Error: Could not find Python executable${NC}"
    exit 1
fi

echo -e "${YELLOW}Using Python: $($PYTHON_CMD --version)${NC}"

# Check if pip is installed
if ! $PYTHON_CMD -m pip --version &> /dev/null; then
    echo -e "${RED}Error: pip is not installed. Please install pip first.${NC}"
    exit 1
fi

# Install requirements from requirements.txt if it exists
if [ -f "requirements.txt" ]; then
    echo -e "${BLUE}Installing dependencies from requirements.txt...${NC}"
    $PYTHON_CMD -m pip install -q --upgrade pip 2>/dev/null || true
    $PYTHON_CMD -m pip install -q -r requirements.txt 2>/dev/null || {
        echo -e "${YELLOW}Warning: Some packages from requirements.txt failed to install${NC}"
    }
    echo -e "${GREEN}✓ Dependencies check complete${NC}\n"
else
    echo -e "${YELLOW}Warning: requirements.txt not found, skipping initial dependency installation${NC}"
fi

# Check if run_with_deps.py exists, if so use it
if [ -f "run_with_deps.py" ]; then
    echo -e "${GREEN}Running with dependency auto-installer...${NC}\n"
    $PYTHON_CMD run_with_deps.py
    exit $?
fi

# Fallback: Simple approach - just run main.py
echo -e "${GREEN}Running main.py...${NC}\n"
$PYTHON_CMD main.py
