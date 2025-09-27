# code2prompt

A Python tool that intelligently splits code repositories into LLM-sized chunks for security analysis and other AI-powered code review tasks. The tool ensures files are never split across chunks and accounts for security prompts in token budgeting.

## Features

- **Smart Token Management**: Accounts for security prompts, headers, footers, and completion reserves in token budgeting
- **No File Splitting**: Files are never split across chunks - each file stays intact
- **Flexible Security Prompt Integration**: Choose how to embed security prompts (none, first part only, or every part)
- **Configurable File Filtering**: Include/exclude files and directories with glob patterns
- **Oversize File Handling**: Multiple policies for files that exceed chunk limits
- **Comprehensive Logging**: Track skipped files and reasons
- **Multiple Token Encodings**: Support for different tiktoken encodings

## Installation

### Using uvx (Recommended)

```bash
uvx code2prompt
```

This will automatically download and run the latest version without requiring local installation.

### Manual Installation

```bash
pip install tiktoken
```

Then download `code2prompt.py` and make it executable:

```bash
chmod +x code2prompt.py
```

## Usage

### Basic Usage

```bash
# Using uvx (recommended)
uvx code2prompt --repo . --security-prompt-file security_prompt.md

# Or with manual installation
python3 code2prompt.py --repo . --security-prompt-file security_prompt.md
```

### Advanced Usage

```bash
uvx code2prompt \
    --repo . \
    --security-prompt-file security_prompt.md \
    --embed-security-prompt first \
    --model-context 262144 \
    --reserve-completion 8000 \
    --safety-margin 2048 \
    --encoding o200k_base \
    --oversize-policy error \
    --log-skipped
```

## Command Line Options

### Core Options

- `--repo PATH`: Path to repository (default: current directory)
- `--outdir PATH`: Output directory for parts (default: `prompts_split`)
- `--security-prompt-file PATH`: Security prompt file (default: `security_prompt.md`)

### Token Management

- `--model-context N`: Maximum model context in tokens (default: 262144)
- `--reserve-completion N`: Reserve tokens for response (default: 8000)
- `--safety-margin N`: Safety margin in tokens (default: 2048)
- `--encoding NAME`: tiktoken encoding: `o200k_base` or `cl100k_base` (default: `o200k_base`)

### Security Prompt Integration

- `--embed-security-prompt MODE`: How to embed security prompt:
  - `none`: Don't embed (account for tokens only)
  - `first`: Embed in first part only
  - `each`: Embed in every part (default)

### File Filtering

- `--include PATTERN`: Add include glob pattern (can be repeated)
- `--exclude PATTERN`: Add exclude glob pattern (can be repeated)
- `--exclude-dir DIR`: Add directory to exclude (can be repeated)
- `--max-file-bytes N`: Maximum size of single file in bytes (default: 800000)
- `--min-file-bytes N`: Minimum size of single file in bytes (default: 10)

### Behavior Options

- `--oversize-policy POLICY`: Behavior for files exceeding part limit:
  - `error`: Exit with error (default)
  - `skip`: Skip the file and log it
  - `allow`: Create separate part with just that file (may exceed model context)
- `--log-skipped`: Print list of skipped files and reasons

## Default File Filters

### Included by Default
- Source code: `.py`, `.ts`, `.tsx`, `.js`, `.go`, `.java`, `.kt`, `.cs`, `.rs`
- Config files: `.yml`, `.yaml`, `.toml`, `.ini`, `.conf`, `.json`
- Documentation: `.md`
- Other: `.proto`, `.graphql`, `.gql`, `Dockerfile`

### Excluded by Default
- Directories: `.git`, `.svn`, `.hg`, `node_modules`, `dist`, `build`, `.venv`, `.mypy_cache`, `__pycache__`, `.idea`, `.vscode`, `target`, `.tox`, `.pytest_cache`
- Files: `*.min.*`, `*.lock`, media files (`*.svg`, `*.png`, `*.jpg`, etc.), archives (`*.zip`, `*.rar`, etc.), binaries (`*.bin`, `*.obj`, `*.class`)
- Temporary files: `*.tmp`, `*.temp`, `*.swp`, `*.bak`, `*.orig`, `*.rej`
- IDE files: `*.sublime-*`, `*.code-workspace`
- Content-based exclusions: Empty files (< 10 bytes), binary files (detected by content)

## Output Format

The tool generates numbered markdown files in the output directory:

```
prompts_split/
├── prompt_part_001.md
├── prompt_part_002.md
└── prompt_part_003.md
```

Each part contains:
1. **Header**: Part number and instructions
2. **Security Prompt** (if configured): The security prompt content
3. **File Contents**: Complete files with absolute paths and code blocks
4. **Footer**: End marker with part number

## Security Prompt

The tool is designed to work with security analysis prompts. The default `security_prompt.md` contains a comprehensive security assessment template that:

- Guides analysis of API endpoints and parameters
- Identifies dangerous operations (file I/O, network calls, etc.)
- Performs deep security analysis across multiple dimensions
- Produces structured findings with CVSS ratings
- Generates actionable remediation plans

## Examples

### Security Analysis of Current Repository

```bash
uvx code2prompt \
    --repo . \
    --security-prompt-file security_prompt.md \
    --embed-security-prompt each \
    --model-context 128000 \
    --reserve-completion 4000 \
    --log-skipped
```

### Large Repository with Custom Filters

```bash
uvx code2prompt \
    --repo /path/to/large/repo \
    --include "**/*.py" \
    --include "**/*.js" \
    --exclude "**/test_*" \
    --exclude "**/migrations/**" \
    --max-file-bytes 500000 \
    --min-file-bytes 50 \
    --oversize-policy skip \
    --log-skipped
```

### Minimal Configuration

```bash
uvx code2prompt --repo . --embed-security-prompt none
```

## Token Budgeting

The tool carefully manages token budgets:

1. **Fixed Overhead**: Security prompt + headers + footers + completion reserve + safety margin
2. **Per-Part Limit**: Model context minus fixed overhead
3. **File Placement**: Files are placed in parts without splitting
4. **Oversize Handling**: Large files are handled according to policy

## Exit Codes

- `0`: Success
- `1`: General error
- `2`: Insufficient budget error
- `3`: Oversize file error (when policy is `error`)

## Requirements

- Python 3.6+
- `tiktoken` library for token counting

## License

This tool is provided as-is for security analysis and code review purposes.
