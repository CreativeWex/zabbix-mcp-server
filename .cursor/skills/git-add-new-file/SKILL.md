---
name: git-add-new-file
description: Automatically stages newly created files with `git add`. Activates ONLY when the agent creates a brand-new file that did not exist before (using Write tool or equivalent). Does NOT activate when an existing file is modified, deleted, or renamed. Trigger terms: new file created, created file, write new file.
---

# git-add-new-file

## When to activate

**Activate** — the agent just created a file that did not previously exist (e.g. via Write tool on a path that was not there before).

**Do NOT activate** — the agent edited, deleted, or renamed an existing file, or no file was created.

## Action

After creating the file, immediately run:

```bash
git add <path/to/new/file>
```

Use the exact path of the newly created file as provided to the Write tool.

## Example

File `zabbix-mcp-server/plan.md` is created for the first time → run:

```bash
git add zabbix-mcp-server/mcp-description.md
```

File `zabbix-mcp-server/README.md` is edited → do nothing.
