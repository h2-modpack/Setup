#!/bin/bash

# UPDATE THIS with your actual project number from the URL
PROJECT_NUMBER="1" 
ORG_NAME="h2-modpack"

WORKFLOW_CONTENT=$(cat <<EOF
name: Auto-add to Project
on:
  issues:
    types: [opened]
  pull_request:
    types: [opened]

jobs:
  add-to-project:
    runs-on: ubuntu-latest
    steps:
      - name: Get Project Data
        uses: actions/add-to-project@v1.0.1
        with:
          project-url: https://github.com/orgs/$ORG_NAME/projects/$PROJECT_NUMBER
          github-token: \${{ secrets.PROJECT_ADD_TOKEN }}
EOF
)

# Loop through all folders in Submodules
for d in Submodules/adamant-*/; do
    [ -d "$d" ] || continue
    
    echo "Configuring automation for: $d"
    mkdir -p "${d}.github/workflows"
    echo "$WORKFLOW_CONTENT" > "${d}.github/workflows/project-auto-add.yml"
    
    cd "$d" || continue
    git add .github/workflows/project-auto-add.yml
    git commit -m "ci: automate project board tracking"
    git push origin main
    cd ../../
done

echo "✅ Automation live across all submodules!"
