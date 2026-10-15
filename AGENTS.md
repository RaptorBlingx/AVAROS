# Agent contribution guidance

Follow `DEVELOPMENT.md` for the team's commit, testing and PR conventions. These rules supplement that guide:

- Before editing, record the repository, remote, intended base branch/commit, working-tree status and active worktrees. Use a dedicated task branch from the agreed base; reuse a suitable task worktree rather than creating duplicate checkouts. Do not switch another worktree's branch or disturb unrelated changes.
- Keep commits scoped to one reviewable concern, stage explicit paths, and use the documented `type(scope): subject` format. Keep agent/workflow documentation changes separate from product fixes.
- Before an authorized publication, refresh remote refs and compare all local branch tips with all remote branches. Check ancestry and patch equivalence: a task commit may already be integrated under another SHA. Do not cherry-pick or publish a second copy of an integrated change.
- State the intended PR base explicitly. Review the complete diff against that base, including integration commits; report exact verification scope, known baseline failures and remaining limitations. Follow the documented merge policy with reviewer approval.
- Prefer one publication branch/PR per review scope. Retain task branches/worktrees until their work and evidence are safely reachable from the agreed integration/checkpoint; remove them only when authorized. Do not use extra long-lived branches as substitutes for immutable release checkpoints.
- Record a checkpoint's source SHA separately from its runtime images, configuration/profile, external-service versions and validation evidence. Keep secrets, database dumps and raw tenant measurements out of Git; use sanitized manifests and references to protected backups.
- Push, merge, create release tags, rewrite history, migrate databases, restart shared services or deploy only when explicitly requested. Never force-push or rewrite shared history to tidy a release.
