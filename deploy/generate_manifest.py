"""
Reads a thunderstore.toml and generates a manifest.json for local deployment.

Usage: python generate_manifest.py <path_to_thunderstore.toml> <output_manifest.json>
"""

import sys
import os
import json
import re



def parse_toml(toml_path):
    """
    Reads thunderstore.toml and returns manifest fields.
    """
    with open(toml_path, "r", encoding="utf-8") as f:
        content = f.read()
        lines = content.splitlines()

    namespace = ""
    name = ""
    description = ""
    version = ""
    website_url = ""
    dependencies = []

    current_section = ""

    for line in lines:
        stripped = line.strip()

        # Track sections
        if stripped.startswith("["):
            current_section = stripped.strip("[]").strip()
            continue

        # Skip empty/comment lines
        if not stripped or stripped.startswith("#"):
            continue

        # Parse key = value
        match = re.match(r'^(\S+)\s*=\s*(.+)$', stripped)
        if not match:
            continue

        key = match.group(1)
        raw_value = match.group(2).strip()

        # Remove quotes from string values
        if raw_value.startswith('"') and raw_value.endswith('"'):
            value = raw_value[1:-1]
        else:
            value = raw_value

        if current_section == "package":
            if key == "namespace":
                namespace = value
            elif key == "name":
                name = value
            elif key == "description":
                description = value
            elif key == "versionNumber":
                version = value
            elif key == "websiteUrl":
                website_url = value
        elif current_section == "package.dependencies":
            # Format: Namespace-Name = "version" -> "Namespace-Name-version"
            dependencies.append(f"{key}-{value}")

    return {
        "namespace": namespace,
        "name": name,
        "description": description,
        "version_number": version,
        "dependencies": dependencies,
        "website_url": website_url,
        "FullName": f"{namespace}-{name}",
    }


def main():
    if len(sys.argv) != 3:
        print("Usage: python generate_manifest.py <thunderstore.toml> <output_manifest.json>")
        sys.exit(1)

    toml_path = sys.argv[1]
    output_path = sys.argv[2]

    if not os.path.isfile(toml_path):
        print(f"Error: '{toml_path}' not found.")
        sys.exit(1)

    manifest = parse_toml(toml_path)

    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")

    print(f"  Generated manifest: {output_path}")


if __name__ == "__main__":
    main()
