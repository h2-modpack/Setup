OLD_OWNER="maybe-adamant" # <--- CHANGED
NEW_OWNER="h2-modpack"    # <--- CHANGED

while read repo; do
  # Skip empty lines
  [ -z "$repo" ] && continue 

  echo "Transferring $repo to $NEW_OWNER..."
  
  gh api --method POST \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    /repos/$OLD_OWNER/$repo/transfer \
    -f new_owner=$NEW_OWNER
  
  # 1-second delay to respect GitHub's API rate limits
  sleep 1

done < repos.txt

echo "Transfer complete!"
