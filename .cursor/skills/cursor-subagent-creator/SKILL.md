---
name: cursor-subagent-creator
description: Creates Cursor-specific AI subagents with isolated context for complex multi-step workflows. Use when creating subagents for Cursor editor specifically, following Cursor's patterns and directories (.cursor/agents/). Triggers on "cursor subagent", "cursor agent". Do NOT use for generic subagent creation outside Cursor (use subagent-creator instead).
---

# Cursor Subagent Creator

## What are Subagents?

Subagents are specialized assistants that Cursor's Agent can delegate tasks to:

- **Isolated context**: Each subagent has its own context window
- **Parallel execution**: Multiple subagents can run simultaneously
- **Specialization**: Configured with specific prompts and expertise
- **Reusable**: Defined once, used in multiple contexts

Use subagents for **complex tasks with multiple steps that benefit from isolated context**. For quick, one-off actions, use skills.

## Subagent File Format

Create a markdown file in `.cursor/agents/` (project) or `~/.cursor/agents/` (user):

```markdown
---
name: agent-name
description: Description of when to use this subagent. The Agent reads this to decide delegation.
model: inherit # or fast, or specific model ID
readonly: false # true to restrict write permissions
is_background: false # true for long-running/background tasks
---

You are an [expert in X].

When invoked:

1. [Step 1]
2. [Step 2]
3. [Step 3]

Report [expected result]:

- [Output format]
- [Metrics or specific information]
```

## Field Reference

| Field           | Required | Default   | Description                                      |
| --------------- | -------- | --------- | ------------------------------------------------ |
| `name`          | No       | Filename  | Unique identifier (kebab-case)                   |
| `description`   | No       | —         | When to use this subagent (read by Agent)        |
| `model`         | No       | `inherit` | `fast`, `inherit`, or specific model ID          |
| `readonly`      | No       | `false`   | If true, write permissions restricted            |
| `is_background` | No       | `false`   | If true, executes in background                  |

## Creation Process

### 1. Choose Location

- **Project**: `.cursor/agents/agent-name.md` — project-specific, commit to version control
- **User**: `~/.cursor/agents/agent-name.md` — available across all projects

Use kebab-case filenames: `security-auditor`, `test-runner`, `debugger`.

### 2. Write a Strong Description

The description is critical for automatic delegation. Be specific about when to use it.

**Good:**
```yaml
description: Security specialist. Use when implementing auth, payments, or handling sensitive data.
description: Validates completed work. Use after tasks are marked done to confirm implementations are functional.
```

**Encourage automatic delegation** with phrases like "Use proactively when...", "Always use for...", "Automatically delegate when...".

**Avoid:** vague descriptions like "Helps with general tasks".

### 3. Write the Prompt

Structure the prompt with:
1. **Identity**: "You are an [expert]..."
2. **When invoked**: Steps to follow
3. **Expected output**: Format and content
4. **Behavior/philosophy**

Keep prompts concise — one clear responsibility, actionable instructions, structured output.

## Quick Template

```markdown
---
name: [agent-name]
description: [Expert in X]. Use when [specific context of when to delegate].
model: inherit
---

You are an [expert in X] specialized in [Y].

When invoked:

1. [First step]
2. [Second step]
3. [Third step]

[Detailed instructions about approach and behavior]

Report [type of result]:

- [Specific format]
- [Information to include]
- [Success criteria]

[Principles or philosophy to follow]
```

## Skills vs Subagents

```
Is the task complex with multiple steps?
├─ YES → Does it require isolated context?
│         ├─ YES → Use SUBAGENT
│         └─ NO → Use SKILL
└─ NO → Is it a single, one-off action?
          ├─ YES → Use slash command or SKILL
          └─ NO → Use SUBAGENT
```

## Invoking Subagents

- **Slash command**: `/verifier confirm that the auth flow is complete`
- **Natural language**: "Use the verifier subagent to confirm the auth flow is complete"
- **Automatic**: Agent delegates based on description when task matches

## Quality Checklist

- [ ] Description is specific about when the Agent should delegate
- [ ] Filename uses kebab-case
- [ ] One clear responsibility (not generic)
- [ ] Prompt is concise but complete
- [ ] Instructions are actionable
- [ ] Output format is well defined
- [ ] `model` is appropriate (`inherit` / `fast` / specific)
- [ ] `readonly` set correctly (if only reads/analyzes)
- [ ] `is_background` set correctly (if long-running)

## After Creating a Subagent

Inform the user:

```
✅ Subagent created successfully!

📁 Location: .cursor/agents/[name].md
🎯 Purpose: [brief description]
🔧 How to invoke:
   - Automatic: The Agent will delegate when it detects [context]
   - Explicit: /[name] [your instruction]
   - Natural: "Use the [name] subagent to [task]"

💡 Tip: Include keywords like "use proactively" in the description
to encourage automatic delegation.
```

## Additional Resources

- For common patterns (verifier, debugger, security-auditor, test-runner, etc.) and complete examples, see [reference.md](reference.md)
