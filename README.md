# Tools

A collection of useful development tools.

## Available Tools

### code2prompt

A Python tool that intelligently splits code repositories into LLM-sized chunks for security analysis and other AI-powered code review tasks. The tool ensures files are never split across chunks and accounts for security prompts in token budgeting.

The main purpose of this tool is to enable splitting projects for LLMs with limited context windows. Instead of manually selecting files or dealing with context overflow, this tool automatically organizes your entire codebase into manageable chunks that fit within your LLM's token limits.

**Key Features:**
- Smart token management with security prompt budgeting
- No file splitting - files stay intact
- Configurable file filtering with glob patterns
- Support for different LLM encodings
- Comprehensive logging of skipped files

**Quick Start:**
```bash
uvx code2prompt --repo . --security-prompt-file security_prompt.md
```

For detailed documentation, see [code2prompt/README.md](code2prompt/README.md).
