#!/bin/bash

ORG_NAME="h2-modpack"
FOLDER_PREFIX="adamant-"
REPO_PREFIX="h2-modpack-"

echo "Initializing master repository..."
git init

# 1. Manually link Core and Lib at the root level
# (Adjust the repo URLs slightly if they are named differently on GitHub)
echo "Linking Core and Lib..."
git submodule add "https://github.com/$ORG_NAME/h2-modpack-coordinator.git" "adamant-modpack-coordinator"
git submodule add "https://github.com/$ORG_NAME/h2-modpack-Lib.git" "adamant-modpack-Lib"

# 2. Loop through the Submodules directory for the standalone mods
echo "Linking standalone modules..."
for d in Submodules/adamant-*/; do
    # Safety check in case the directory is empty
    [ -d "$d" ] || continue

    # Strip the trailing slash (e.g., "Submodules/adamant-BraidFix")
    folder_path="${d%/}"
    
    # Isolate just the folder name (e.g., "adamant-BraidFix")
    folder_name=$(basename "$folder_path")

    # Extract the suffix (e.g., "BraidFix")
    suffix="${folder_name#$FOLDER_PREFIX}"
    

    repo_name="${REPO_PREFIX}${suffix}"
    repo_url="https://github.com/$ORG_NAME/$repo_name.git"
    
    echo "Linking '$repo_name' at local path '$folder_path'..."
    
    # Add the submodule, telling Git to keep it inside the Submodules/ directory
    git submodule add "$repo_url" "$folder_path"
done

echo "✅ All submodules linked successfully! Check your new .gitmodules file."
