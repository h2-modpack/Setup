Write-Host "Starting Bulk DevOps Initialization..." -ForegroundColor Cyan

# 1. Define the root directory (Step out of the Setup folder)
$setupDir = (Get-Location).Path
$rootDir = Split-Path -Path $setupDir -Parent

$targets = @()
$targets += Join-Path $rootDir "adamant-modpack-coordinator"
$targets += Join-Path $rootDir "adamant-modpack-Lib"

# Dynamically grab all folders inside 'Submodules' that start with 'adamant-'
$submodulesDir = Join-Path $rootDir "Submodules"
if (Test-Path $submodulesDir) {
    $targets += Get-ChildItem -Path $submodulesDir -Directory -Filter "adamant-*" | Select-Object -ExpandProperty FullName
}

# 2. The Master Loop
foreach ($repoPath in $targets) {
    if (-not (Test-Path $repoPath)) { 
        Write-Host "Skipping: Could not find $repoPath" -ForegroundColor Yellow
        continue 
    }
    
    Set-Location $repoPath
    $repoName = Split-Path $repoPath -Leaf
    Write-Host "`n=======================================================" -ForegroundColor Magenta
    Write-Host "Setting up DevOps for: $repoName" -ForegroundColor Cyan
    Write-Host "=======================================================" -ForegroundColor Magenta

    # --- CI Gatekeeper ---
    New-Item -ItemType Directory -Force -Path ".github\workflows" | Out-Null
    $yaml = @'
name: Lua Linter (Luacheck)
on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4
      - name: Setup Lua
        uses: leafo/gh-actions-lua@v10
        with:
          luaVersion: "5.2"
      - name: Setup Luarocks
        uses: leafo/gh-actions-luarocks@v4
      - name: Install Luacheck
        run: luarocks install luacheck
      - name: Run Luacheck
        run: luacheck src/
'@
    Set-Content -Path ".github\workflows\luacheck.yaml" -Value $yaml -Encoding UTF8
    Write-Host "  -> CI Workflow created." -ForegroundColor Green

    # --- Local Hook (Tracked Version) ---
    New-Item -ItemType Directory -Force -Path ".githooks" | Out-Null
$hook = @'
#!/bin/bash
echo "Running Luacheck before commit..."
luacheck src
RESULT=$?
if [ $RESULT -ne 0 ]; then
    echo "[FAIL] Luacheck failed! Please fix errors before committing."
    exit 1
fi
echo "[SUCCESS] Luacheck passed!"
exit 0
'@
Set-Content -Path ".githooks\pre-commit" -Value $hook -Encoding ASCII
    Write-Host "  -> Tracked Git Hook created." -ForegroundColor Green

    # Tell local Git to use this new folder
    git config core.hooksPath .githooks

    # --- Template .luacheckrc ---
    $luacheckrc = @'
std = "lua52"
max_line_length = 120
globals = { 
    "rom", 
    "public", 
    "config", 
    "modutil", 
    "game", 
    "chalk", 
    "reload", 
    "_PLUGIN" 
    }
read_globals = { 
    "imgui", 
    "import_as_fallback", 
    "import" 
    }
'@
    Set-Content -Path ".luacheckrc" -Value $luacheckrc -Encoding UTF8
    Write-Host "  -> Template .luacheckrc created." -ForegroundColor Green

    # --- Commit and Push ---
    git add .
    git commit -m "chore: automated devops and linter setup"
    git push origin main
    Write-Host "  -> Pushed to GitHub." -ForegroundColor Green

    # --- Lock the Branch ---
    $jsonPayload = @'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["lint"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": {
    "required_approving_review_count": 0
  },
  "restrictions": null
}
'@
    # The :owner/:repo magic string automatically reads the .git config of the current folder
    $jsonPayload | gh api -X PUT repos/:owner/:repo/branches/main/protection --input - --silent
    Write-Host "  -> Branch locked! PRs and Luacheck are now mandatory." -ForegroundColor Green
}

# Return to the Setup directory when finished
Set-Location $setupDir
Write-Host "`n✅ All submodules successfully configured and locked!" -ForegroundColor Green