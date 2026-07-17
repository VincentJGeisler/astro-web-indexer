# Plate Solving — Open Questions for High-Level AI

Questions blocking or clarifying `docs/SPEC-plate-solving.md`. Each entry:
context -> question. Move to "Resolved" once answered.

## Resolved
- **Verification environment:** Docker is unavailable on the local dev Mac.
  SSH access to the remote Docker host **10.3.1.76** (user `vince`, host
  `dockserver`, Docker 29.2.1) is confirmed. Workflow = push `feature/plate-solving`
  to origin, then pull the branch on .76 and verify in an ISOLATED test stack
  (separate container names + port 8101 + separate DB volume) that shares only
  the READ-ONLY FITS mount (`/mnt/astronomy`). The live deployment at
  10.3.1.76:**8100** (containers `*-awi`) is left untouched until Vince approves.

## Open
(none yet)
