#!/bin/bash
#
# Pancake Deployment Script
# Installs the Pancake utility to your local bin directory
#

set -e  # Exit on error

# Colorful output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🥞 Deploying Pancake...${NC}"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PANCAKE_SCRIPT="$SCRIPT_DIR/pancake.py"
USER_BIN="$HOME/bin"

# Check if the script exists
if [ ! -f "$PANCAKE_SCRIPT" ]; then
    echo -e "${RED}Error: Cannot find pancake.py in the current directory.${NC}"
    exit 1
fi

# Make sure ~/bin exists
if [ ! -d "$USER_BIN" ]; then
    echo -e "${YELLOW}Creating $USER_BIN directory...${NC}"
    mkdir -p "$USER_BIN"
fi

# Check if ~/bin is in PATH
if [[ ":$PATH:" != *":$USER_BIN:"* ]]; then
    echo -e "${YELLOW}Warning: $USER_BIN is not in your PATH.${NC}"
    echo -e "${YELLOW}Consider adding this line to your shell profile (~/.bashrc, ~/.zshrc, etc.):${NC}"
    echo -e "    ${GREEN}export PATH=\"\$HOME/bin:\$PATH\"${NC}"
fi

# Make script executable
echo -e "${YELLOW}Making pancake.py executable...${NC}"
chmod +x "$PANCAKE_SCRIPT"

# Copy to ~/bin
echo -e "${YELLOW}Installing to $USER_BIN/pancake...${NC}"
cp "$PANCAKE_SCRIPT" "$USER_BIN/pancake"

# Test the installation
if command -v pancake &> /dev/null; then
    echo -e "${GREEN}✅ Pancake has been successfully installed!${NC}"

    # Print version to confirm installation
    VERSION=$(pancake --version 2>/dev/null)
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Installed $VERSION${NC}"
    fi

    echo -e "${GREEN}You can now run 'pancake' from anywhere.${NC}"
else
    echo -e "${YELLOW}Pancake was installed to $USER_BIN/pancake${NC}"
    echo -e "${YELLOW}But it's not accessible in your current shell.${NC}"
    echo -e "${YELLOW}Try:${NC}"
    echo -e "  ${GREEN}export PATH=\"\$HOME/bin:\$PATH\"${NC}"
    echo -e "${YELLOW}Or open a new terminal window.${NC}"
fi

echo -e "${GREEN}🥞 Happy flattening!${NC}"