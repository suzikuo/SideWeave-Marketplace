# SideWeave Marketplace

This repository is the public catalog for SideWeave. The app reads marketplace.json and publishers.json from the master branch using fixed raw GitHub URLs.

## Catalog rules

- marketplace.json is the public catalog. Each item has a latest string pointing to an entry in versions; clients do not calculate the newest version.
- publishers.json contains publisher key IDs, Minisign public keys and key states: active, retired or revoked.
- Every version provides exact HTTPS URLs for the ZIP, .minisig and .sha256 assets. The repository field is display metadata; clients never derive download URLs from it.
- Unknown schema versions, missing latest pointers, unknown publishers and malformed assets fail validation.
- verified: true means maintainers reviewed the catalog entry. It is not a security guarantee.

The SideWeave app release script reads the official publisher key from this repository's publishers.json and pins it into the app. The publisher key is separate from the Tauri updater key. Native packages, including official plugins, require first-use publisher trust confirmation in the app.

## Validate locally

Run the validator before pushing marketplace changes. Set MINISIGN_EXE to the path of minisign.exe, then run:

    $env:MINISIGN_EXE = 'F:\path\to\minisign.exe'
    python .\tools\validate_marketplace.py
    Remove-Item Env:MINISIGN_EXE

The validator downloads referenced assets, checks checksums and Minisign signatures, checks package manifests, and never executes plugin code.
