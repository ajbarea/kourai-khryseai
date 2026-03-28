#!/bin/bash
# Phase 1: HF-Mount Setup Script
# This script sets up HuggingFace Storage Buckets for agent artifact storage.
#
# Usage:
#   bash scripts/setup-hf-mount.sh
#
# Prerequisites:
#   - HuggingFace account at https://huggingface.co
#   - HF API token with write permissions
#   - huggingface_hub Python package installed

set -e

echo "🚀 Kourai Khryseai - Phase 1: HF-Mount Setup"
echo "=============================================="
echo ""

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Check prerequisites
echo -e "${BLUE}Step 1: Checking prerequisites...${NC}"

# Use uv run for Python execution (respects project venv)
PYTHON="uv run --no-active python"
UV_PIP="uv pip"

if ! command -v uv &> /dev/null; then
    echo -e "${RED}❌ uv not found. Please install uv (part of Kourai setup)${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Using uv for Python execution${NC}"

# Check huggingface_hub
if ! $PYTHON -c "import huggingface_hub" 2>/dev/null; then
    echo -e "${YELLOW}⚠ huggingface_hub not installed. Installing...${NC}"
    $UV_PIP install huggingface-hub
fi
echo -e "${GREEN}✓ huggingface_hub installed${NC}"

# Step 2: Get HF token
echo ""
echo -e "${BLUE}Step 2: HuggingFace Authentication${NC}"

# Check if HF_TOKEN already set
if [ -n "$HF_TOKEN" ]; then
    echo -e "${GREEN}✓ HF_TOKEN already set in environment${NC}"
elif [ -f .env.hf ]; then
    source .env.hf
    if grep -q "hf_" .env.hf 2>/dev/null; then
        echo -e "${GREEN}✓ HF_TOKEN found in .env.hf${NC}"
    else
        echo -e "${YELLOW}⚠ .env.hf exists but token not set${NC}"
    fi
else
    echo -e "${YELLOW}⚠ No HF_TOKEN found${NC}"
    echo ""
    echo "Please get your token from: https://huggingface.co/settings/tokens"
    echo "Create a NEW token with 'write' scope."
    echo ""
    read -p "Enter your HF token (or press Enter to skip): " HF_TOKEN_INPUT
    
    if [ -n "$HF_TOKEN_INPUT" ]; then
        cat > .env.hf << EOF
# HuggingFace API Token for HF-Mount
# Set up on $(date)
HF_TOKEN=$HF_TOKEN_INPUT
EOF
        echo -e "${GREEN}✓ Token saved to .env.hf${NC}"
        export HF_TOKEN="$HF_TOKEN_INPUT"
    else
        echo -e "${YELLOW}⚠ Token not provided. You'll need to set HF_TOKEN manually.${NC}"
    fi
fi

# Step 3: Get HF username
echo ""
echo -e "${BLUE}Step 3: Detecting HuggingFace username...${NC}"

if [ -n "$HF_TOKEN" ]; then
    HF_USERNAME=$($PYTHON << 'PYTHON_EOF'
import os
from huggingface_hub import HfApi
try:
    api = HfApi()
    user_info = api.whoami()
    print(user_info["name"])
except Exception as e:
    print(f"Error: {e}")
    exit(1)
PYTHON_EOF
)
    
    if [ $? -eq 0 ] && [ -n "$HF_USERNAME" ]; then
        echo -e "${GREEN}✓ HuggingFace username: $HF_USERNAME${NC}"
    else
        read -p "Enter your HuggingFace username: " HF_USERNAME
    fi
else
    read -p "Enter your HuggingFace username: " HF_USERNAME
fi

# Step 4: Create buckets
echo ""
echo -e "${BLUE}Step 4: Creating HuggingFace Storage Buckets...${NC}"

if [ -z "$HF_TOKEN" ]; then
    echo -e "${YELLOW}⚠ Skipping bucket creation (no HF_TOKEN)${NC}"
    echo "   Run this when you have your token:"
    echo "   export HF_TOKEN=hf_..."
    echo "   bash scripts/setup-hf-mount.sh"
else
    BUCKET_NAME="kourai-artifacts"
    FULL_BUCKET="$HF_USERNAME/$BUCKET_NAME"
    
    echo "Creating buckets for: $FULL_BUCKET"
    
    # Create main bucket
    $PYTHON << PYTHON_EOF
import os
from huggingface_hub import create_bucket
os.environ['HF_TOKEN'] = "$HF_TOKEN"
try:
    # Create main bucket
    result = create_bucket("$FULL_BUCKET", private=True)
    print(f"✓ Created bucket: {result}")
except Exception as e:
    if "exists" in str(e).lower():
        print(f"✓ Bucket already exists: $FULL_BUCKET")
    else:
        print(f"⚠ Error creating bucket: {e}")
PYTHON_EOF

    # Create agent sub-buckets
    AGENTS=("dokimasia" "techne" "kallos" "metis" "mneme" "other")
    
    for agent in "${AGENTS[@]}"; do
        $PYTHON << PYTHON_EOF
import os
import sys
from huggingface_hub import create_bucket
os.environ['HF_TOKEN'] = "$HF_TOKEN"
try:
    result = create_bucket("$FULL_BUCKET/$agent", private=True)
    print(f"✓ Created sub-bucket: $agent")
except Exception as e:
    if "exists" in str(e).lower():
        print(f"✓ Sub-bucket already exists: $agent")
    else:
        print(f"⚠ Error creating sub-bucket: {e}")
        sys.exit(1)
PYTHON_EOF
    done
fi

# Step 5: Install hf-mount
echo ""
echo -e "${BLUE}Step 5: HF-Mount Installation${NC}"

if command -v hf-mount &> /dev/null; then
    HF_MOUNT_VERSION=$(hf-mount --version 2>/dev/null || echo "unknown")
    echo -e "${GREEN}✓ hf-mount already installed (version: $HF_MOUNT_VERSION)${NC}"
else
    echo -e "${YELLOW}⚠ hf-mount not found in PATH${NC}"
    echo "Installing hf-mount..."
    
    # Detect OS
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "Detected Linux"
        curl -fsSL https://raw.githubusercontent.com/huggingface/hf-mount/main/install.sh | sh
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "Detected macOS"
        # Check for macFUSE
        if ! pkgutil --pkg-info com.github.osxfuse.pkg >/dev/null 2>&1; then
            echo -e "${YELLOW}⚠ macFUSE not installed. Install with: brew install macfuse${NC}"
        fi
        curl -fsSL https://raw.githubusercontent.com/huggingface/hf-mount/main/install.sh | sh
    else
        echo -e "${RED}❌ Unsupported OS: $OSTYPE${NC}"
        echo "Please install hf-mount manually from:"
        echo "https://github.com/huggingface/hf-mount/releases"
        exit 1
    fi
    
    # Add to PATH if installed to ~/.local/bin/
    if [ -f "$HOME/.local/bin/hf-mount" ]; then
        if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
            echo "" >> ~/.bashrc
            echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> ~/.bashrc
            export PATH="$HOME/.local/bin:$PATH"
            echo -e "${GREEN}✓ Added ~/.local/bin to PATH${NC}"
        fi
    fi
fi

# Step 6: Configuration summary
echo ""
echo -e "${GREEN}✅ Phase 1 Setup Complete!${NC}"
echo ""
echo -e "${BLUE}Configuration Summary:${NC}"
echo "  HuggingFace Username: $HF_USERNAME"
echo "  Main Bucket: $HF_USERNAME/kourai-artifacts"
echo "  Sub-buckets: dokimasia, techne, kallos, metis, mneme"
echo "  HF Token File: .env.hf"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo "1. Start hf-mount daemon:"
echo "   hf-mount start bucket $HF_USERNAME/kourai-artifacts/dokimasia /tmp/hf-dokimasia"
echo ""
echo "2. Verify mount:"
echo "   ls -la /tmp/hf-dokimasia/"
echo ""
echo "3. Start Kourai with Docker Compose:"
echo "   docker-compose up dokimasia"
echo ""
echo "4. Check HF Hub for artifacts:"
echo "   https://huggingface.co/buckets/$HF_USERNAME/kourai-artifacts"
echo ""
echo -e "${YELLOW}Documentation:${NC}"
echo "  - Full guide: scripts/../files/PHASE1_IMPLEMENTATION.md"
echo "  - HF-Mount docs: https://github.com/huggingface/hf-mount"
echo "  - HF Buckets docs: https://huggingface.co/docs/hub/storage-buckets"
