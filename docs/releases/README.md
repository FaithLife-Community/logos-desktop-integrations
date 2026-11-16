# Making a release

1. Bump the version in `VERSION` (the installer copies it to `~/.local/share/logos-plasma/VERSION`,
   which Ou Dedetai compares with the latest release to offer updates) and in each
   `plasmoids/*/metadata.json`.
2. Write `docs/releases/vX.Y.Z.md`.
3. After merging to `main`:

       gh release create vX.Y.Z --repo FaithLife-Community/logos-desktop-integrations --target main \
           --title "vX.Y.Z" --notes-file docs/releases/vX.Y.Z.md

   Make sure the release PR is merged first: the tag is made from `main` as it is at that moment.
