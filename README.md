# SideWeave Marketplace repository

This directory is the starter content for the separate public repository `suzikuo/sideweave-marketplace`. Copy its contents to that repository's root when creating it. The app reads the two JSON files from the repository's `main` branch using fixed raw GitHub URLs.

## Files and rules

- `marketplace.json` is the public catalog. Every item has a `latest` string pointing to one entry in `versions`; clients do not calculate the newest version.
- `publishers.json` contains publisher key IDs, Minisign public keys and key states (`active`, `retired`, `revoked`).
- Each version provides exact HTTPS URLs for the ZIP, `.minisig` and `.sha256` assets. `repository` is display metadata; the app never derives download URLs from it.
- Unknown `schema_version` values, missing latest pointers, unknown publishers and malformed assets fail validation.
- `verified: true` means the catalog entry was reviewed by the marketplace maintainers. It is not a security guarantee.

Before adding official native packages, generate a dedicated SideWeave plugin signing key, add its public key here, and set the matching public key's base64 payload (without its `.pub` comment line) as the GitHub Actions repository variable `SIDEWEAVE_OFFICIAL_PUBLISHER_KEY` in `sidebar-tauri`. The app pins that value at build time; this public key is separate from the Tauri updater key.

Pull requests run the static validator in `.github/workflows/validate.yml`. It downloads package assets, verifies checksums and Minisign signatures, checks package manifests, and never executes plugin code.
