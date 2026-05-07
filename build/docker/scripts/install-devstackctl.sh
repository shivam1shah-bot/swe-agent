#!/bin/bash
# install-devstackctl.sh
# Installs devstackctl CLI from razorpay/devstack-v2 (private repo)
#
# Warnings are issued instead of failing the build if GITHUB_TOKEN is missing
# or installation fails. This allows builds to proceed without devstackctl.

set -e

INSTALL_DIR="/root/.devstack/bin"
REPO="razorpay/devstack-v2"
VERSION="v0.5.0"

# Detect architecture
ARCH=$(uname -m)
if [ "$ARCH" = "aarch64" ]; then
    DEVSTACK_ARCH="arm64"
else
    DEVSTACK_ARCH="amd64"
fi

OS="linux"

echo "Installing devstackctl (arch: ${OS}-${DEVSTACK_ARCH})..."

# Create installation directory
mkdir -p "$INSTALL_DIR"

# Read GitHub token from BuildKit secret if available
if [ -f /run/secrets/github_token ]; then
    export GITHUB_TOKEN=$(cat /run/secrets/github_token)
fi

# Download and install devstackctl
if [ -n "$GITHUB_TOKEN" ]; then
    echo "Downloading $VERSION devstackctl for ${OS}-${DEVSTACK_ARCH}..."

    # Use gh CLI to download from GitHub releases (supports private repos)
    # gh CLI uses GH_TOKEN environment variable for authentication
    export GH_TOKEN="$GITHUB_TOKEN"

    ASSET_NAME="devstackctl-${OS}-${DEVSTACK_ARCH}"
    echo "Downloading asset: $ASSET_NAME from $REPO $VERSION"

    # Download to temp location first, then move to final location
    # Warn but continue on failure
    if gh release download "$VERSION" \
        --repo "$REPO" \
        --pattern "$ASSET_NAME" \
        --dir "$INSTALL_DIR" 2>&1; then

        # Verify downloaded file exists
        if [ -f "$INSTALL_DIR/$ASSET_NAME" ]; then
            # Rename to devstackctl and make executable
            mv "$INSTALL_DIR/$ASSET_NAME" "$INSTALL_DIR/devstackctl"
            chmod +x "$INSTALL_DIR/devstackctl"
            echo "devstackctl installed successfully"

            # Initialize devstack environment with default configuration
            echo "Initializing devstack environment..."
            if "$INSTALL_DIR/devstackctl" init --workdir /root/.devstack 2>&1; then
                echo "devstack environment initialized successfully"
            else
                echo "WARNING: devstack initialization failed, continuing..."
            fi
        else
            echo "WARNING: Asset $ASSET_NAME not found after download, continuing..."
        fi
    else
        echo "WARNING: devstackctl download failed (gh release download error), continuing..."
    fi
else
    echo "WARNING: GITHUB_TOKEN not provided, skipping devstackctl installation"
fi

echo "devstackctl installation complete"
