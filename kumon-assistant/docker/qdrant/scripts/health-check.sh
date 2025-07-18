#!/bin/bash
set -e

# Check if Qdrant is responding
if curl -f -s http://localhost:6333/health > /dev/null 2>&1; then
    echo "Qdrant is healthy"
    exit 0
else
    echo "Qdrant is not responding"
    exit 1
fi 