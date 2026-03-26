#!/bin/bash

ORG_NAME="h2-modpack"
FOLDER_PREFIX="adamant-"
REPO_PREFIX="h2-modpack-"

for d in */; do
    # Strip the trailing slash
    folder_name="${d%/}"

    # Only process if it's a git repo AND starts with "adamant-"
    if [ -d "$folder_name/.git" ] && [[ "$folder_name" == "$FOLDER_PREFIX"* ]]; then
        
        # Extract the suffix (e.g., grabs "BraidFix" from "adamant-BraidFix")
        suffix="${folder_name#$FOLDER_PREFIX}"
        
        # Construct the true repo name (e.g., "h2-modpack-BraidFix")
        repo_name="${REPO_PREFIX}${suffix}"
        
        echo "Mapping folder '$folder_name' -> actual repo '$repo_name'..."
        
        cd "$folder_name" || continue
        git remote set-url origin "https://github.com/$ORG_NAME/$repo_name.git"
        cd ..
        
    elif [ -d "$folder_name/.git" ]; then
        echo "⚠️ Skipping '$folder_name': Doesn't match the $FOLDER_PREFIX pattern."
    fi
done

echo "✅ All local remotes updated successfully!"
