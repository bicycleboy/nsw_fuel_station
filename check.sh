#!/bin/bash

INTEGRATION="nsw_fuel_ui"
COMPONENT_DIR="custom_components/$INTEGRATION"
MANIFEST="$COMPONENT_DIR/manifest.json"
INIT="$COMPONENT_DIR/__init__.py"
CONFIG_FLOW="$COMPONENT_DIR/config_flow.py"
CONST="$COMPONENT_DIR/const.py"

echo "Checking custom integration: $INTEGRATION"

# 1️⃣ Folder exists
if [ -d "$COMPONENT_DIR" ]; then
    echo "✅ Folder exists: $COMPONENT_DIR"
else
    echo "❌ Folder missing: $COMPONENT_DIR"
fi

# 2️⃣ __init__.py exists
if [ -f "$INIT" ]; then
    echo "✅ __init__.py exists"
else
    echo "❌ __init__.py missing"
fi

# 3️⃣ manifest.json exists
if [ -f "$MANIFEST" ]; then
    echo "✅ manifest.json exists"
else
    echo "❌ manifest.json missing"
fi

# 4️⃣ manifest.json domain matches folder
if [ -f "$MANIFEST" ]; then
    DOMAIN_JSON=$(jq -r '.domain' "$MANIFEST")
    if [ "$DOMAIN_JSON" == "$INTEGRATION" ]; then
        echo "✅ manifest.json domain matches folder: $DOMAIN_JSON"
    else
        echo "❌ manifest.json domain mismatch: $DOMAIN_JSON"
    fi
fi

# 5️⃣ config_flow.py exists
if [ -f "$CONFIG_FLOW" ]; then
    echo "✅ config_flow.py exists"
else
    echo "❌ config_flow.py missing"
fi

# 6️⃣ DOMAIN in const.py matches folder
if [ -f "$CONST" ]; then
    DOMAIN_CONST=$(grep '^DOMAIN' "$CONST" | cut -d'"' -f2)
    if [ "$DOMAIN_CONST" == "$INTEGRATION" ]; then
        echo "✅ const.py DOMAIN matches folder: $DOMAIN_CONST"
    else
        echo "❌ const.py DOMAIN mismatch: $DOMAIN_CONST"
    fi
fi

echo "Checklist complete. Make sure HA is restarted after any fixes."

