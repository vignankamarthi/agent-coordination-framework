#!/bin/bash
# Setup MCP environment by sourcing API key from Docker's .env file

# Find the project root (parent of .mcp directory)
if [ -n "${BASH_SOURCE[0]}" ]; then
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
else
    SCRIPT_DIR="$( cd "$( dirname "$0" )" && pwd )"
fi

PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Extract LANGSMITH_API_KEY from docker/.env
DOCKER_ENV_PATH="$PROJECT_ROOT/docker/.env"
LANGSMITH_API_KEY=$(grep "^LANGSMITH_API_KEY=" "$DOCKER_ENV_PATH" 2>/dev/null | cut -d '=' -f2)

if [ -z "$LANGSMITH_API_KEY" ]; then
    echo "Error: LANGSMITH_API_KEY not found in docker/.env"
    exit 1
fi

# Export for current session
export LANGSMITH_API_KEY=$LANGSMITH_API_KEY

echo "MCP environment configured successfully"
echo "LANGSMITH_API_KEY has been set for this session"