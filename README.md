# Tools

A collection of useful development tools.

## Available Tools

### repo2prompt

A Python tool that intelligently splits code repositories into LLM-sized chunks for security analysis and other AI-powered code review tasks. The tool ensures files are never split across chunks and accounts for security prompts in token budgeting.

The main purpose of this tool is to enable splitting projects for LLMs with limited context windows. Instead of manually selecting files or dealing with context overflow, this tool automatically organizes your entire codebase into manageable chunks that fit within your LLM's token limits.

**Key Features:**
- Smart token management with security prompt budgeting
- No file splitting - files stay intact
- Configurable file filtering with glob patterns
- Support for different LLM encodings
- Comprehensive logging of skipped files
- Content-based filtering (binary detection, empty file exclusion)

**Quick Start:**
```bash
# Using uv run (recommended)
uv run repo2prompt/repo2prompt.py --repo . --security-prompt-file repo2prompt/security_prompt.md

# Or with Python directly
python3 repo2prompt/repo2prompt.py --repo . --security-prompt-file repo2prompt/security_prompt.md
```

For detailed documentation, see [repo2prompt/README.md](repo2prompt/README.md).
