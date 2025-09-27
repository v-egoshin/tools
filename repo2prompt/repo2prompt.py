#!/usr/bin/env python3
# code2prompt.py
#
# Splits repository into multiple Markdown parts for LLM so that:
#  - security_prompt is accounted for in budget (and optionally embedded in parts);
#  - files are NEVER SPLIT
#  - skipped files and reasons can be logged (--log-skipped)
#
# Examples:
#   python3 code2prompt.py \
#       --repo . \
#       --security-prompt-file security_prompt.md \
#       --embed-security-prompt first \
#       --model-context 262144 \
#       --reserve-completion 8000 \
#       --safety-margin 2048 \
#       --encoding o200k_base \
#       --oversize-policy error \
#       --log-skipped
#
# Oversize policies:
#   - error (default): if one file > part limit → EXIT 3 with message.
#   - skip: such file is skipped (logged as [skipped] oversize>limit).
#   - allow: creates separate part ONLY with this file (may exceed model context —
#            script will warn). Use consciously.

import argparse
import fnmatch
import os
import pathlib
import sys
from typing import List, Tuple

try:
    import tiktoken
except Exception:
    print("tiktoken is not installed. Install: pip install tiktoken", file=sys.stderr)
    raise

DEFAULT_EXCLUDE_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "dist", "build",
    ".venv", ".mypy_cache", "__pycache__", ".idea", ".vscode",
    "target", ".tox", ".pytest_cache",
}

DEFAULT_EXCLUDE_GLOBS = [
    "**/*.min.*",
    "**/*.lock",
    "**/*.svg", "**/*.png", "**/*.jpg", "**/*.jpeg", "**/*.gif", "**/*.ico",
    "**/*.pdf", "**/*.zip", "**/*.rar", "**/*.7z",
    "**/*.mp4", "**/*.mp3", "**/*.mov", "**/*.avi",
    "**/*.bin", "**/*.obj", "**/*.class",
    "**/*.tmp", "**/*.temp", "**/*.swp", "**/*.bak", "**/*.orig", "**/*.rej",
    "**/*.sublime-*", "**/*.code-workspace",
]

DEFAULT_INCLUDE_GLOBS = [
    "**/*.py", "**/*.ts", "**/*.tsx", "**/*.js", "**/*.go",
    "**/*.java", "**/*.kt", "**/*.cs",
    "**/*.proto", "**/*.graphql", "**/*.gql",
    "**/*.rs",
    "**/*.yml", "**/*.yaml", "**/*.toml", "**/*.ini", "**/*.conf",
    "**/*.json", "Dockerfile", "**/Dockerfile",
    "**/*.md",
]

PART_HEADER_TEMPLATE = (
    "# Repository Context (part {i}/{n})\n\n"
    "Notes:\n"
    "- Files are concatenated below. Each section starts with an absolute path.\n"
    "- Maintain state across parts; do not re-summarize previous parts.\n\n"
)

FILE_BLOCK_TEMPLATE = "\n\n---\n# {path}\n\n```\n{content}\n```\n"

END_FOOTER_TEMPLATE = "\n\n---\nEND OF PART {i}/{n}\n"

def is_binary_file(p: pathlib.Path) -> bool:
    """Check if file is binary by examining first 1024 bytes."""
    try:
        with p.open('rb') as f:
            chunk = f.read(1024)
            return b'\0' in chunk
    except Exception:
        return True

def is_meaningful_file(p: pathlib.Path, min_size: int = 10) -> bool:
    """Check if file has meaningful content (not empty or whitespace-only)."""
    try:
        size = p.stat().st_size
        if size < min_size:
            return False
        if size == 0:
            return False
        return True
    except Exception:
        return False

def read_text_safe(p: pathlib.Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        try:
            return p.read_text(encoding="latin-1", errors="replace")
        except Exception:
            return ""

def compile_encoder(encoding_name: str):
    try:
        return tiktoken.get_encoding(encoding_name)
    except KeyError:
        return tiktoken.get_encoding("cl100k_base")

def count_tokens(encoder, text: str) -> int:
    return len(encoder.encode(text))

def match_any(path_str: str, patterns: List[str]) -> bool:
    """Check if path matches any of the glob patterns."""
    path_obj = pathlib.Path(path_str)
    for pattern in patterns:
        if pattern.startswith('**/'):
            # Handle recursive patterns
            if fnmatch.fnmatch(path_str, pattern):
                return True
            # Also check if the pattern matches the filename
            if fnmatch.fnmatch(path_obj.name, pattern[3:]):
                return True
        else:
            if fnmatch.fnmatch(path_str, pattern):
                return True
    return False

def collect_files(repo: pathlib.Path,
                  include_globs: List[str],
                  exclude_globs: List[str],
                  exclude_dirs: List[str],
                  max_file_bytes: int,
                  min_file_bytes: int = 10,
                  log_skipped: bool = False) -> List[pathlib.Path]:
    results: List[pathlib.Path] = []
    skipped: List[Tuple[pathlib.Path, str]] = []
    repo = repo.resolve()
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith(".git")]
        root_path = pathlib.Path(root)
        for name in sorted(files):
            p = root_path / name
            rel = str(p.relative_to(repo))
            try:
                if p.stat().st_size > max_file_bytes:
                    skipped.append((p, f"size>{max_file_bytes}"))
                    continue
            except Exception:
                skipped.append((p, "stat-error"))
                continue
            
            # Additional content-based filtering
            if not is_meaningful_file(p, min_file_bytes):
                skipped.append((p, "empty-or-too-small"))
                continue
            
            if is_binary_file(p):
                skipped.append((p, "binary-content"))
                continue
            
            include_ok = (not include_globs) or match_any(rel, include_globs)
            exclude_hit = match_any(rel, exclude_globs)
            if include_ok and not exclude_hit:
                results.append(p)
            else:
                reason = []
                if not include_ok:
                    reason.append("!include")
                if exclude_hit:
                    reason.append("exclude-glob")
                skipped.append((p, ",".join(reason) if reason else "other"))
    if log_skipped:
        for path, why in skipped:
            print(f"[skipped] {path} ({why})")
    return results

def main():
    ap = argparse.ArgumentParser(description="Split repository into LLM-sized chunks with security prompt budget (no file splitting).")
    ap.add_argument("--repo", default=".", help="Path to repository.")
    ap.add_argument("--outdir", default="prompts_split", help="Output directory for parts.")
    ap.add_argument("--encoding", default="o200k_base", help="tiktoken encoding: o200k_base/cl100k_base.")
    ap.add_argument("--model-context", type=int, default=262144, help="Max model context (tokens).")
    ap.add_argument("--reserve-completion", type=int, default=8000, help="Reserve for response.")
    ap.add_argument("--safety-margin", type=int, default=2048, help="Safety margin (tokens).")
    ap.add_argument("--security-prompt-file", default="security_prompt.md", help="Security prompt file.")
    ap.add_argument(
        "--embed-security-prompt",
        choices=("none", "first", "each"),
        default="each",
        help="Embed security prompt: none (don't embed), first (in first part), each (in every part)."
    )
    ap.add_argument("--max-file-bytes", type=int, default=800_000, help="Max size of single file (bytes).")
    ap.add_argument("--min-file-bytes", type=int, default=10, help="Min size of single file (bytes).")
    ap.add_argument("--include", action="append", default=[], help="Add include-glob (can be repeated).")
    ap.add_argument("--exclude", action="append", default=[], help="Add exclude-glob (can be repeated).")
    ap.add_argument("--exclude-dir", action="append", default=[], help="Add exclude-dir (can be repeated).")
    ap.add_argument(
        "--log-skipped",
        action="store_true",
        help="Print list of skipped files and reason (exclude/size/dir/oversize)."
    )
    ap.add_argument(
        "--oversize-policy",
        choices=("error", "skip", "allow"),
        default="error",
        help="Behavior if ONE file exceeds part limit: error|skip|allow (see script header)."
    )

    args = ap.parse_args()

    repo = pathlib.Path(args.repo).resolve()
    outdir = pathlib.Path(args.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)

    encoder = compile_encoder(args.encoding)

    # Security prompt
    sp_path = pathlib.Path(args.security_prompt_file)
    security_prompt = read_text_safe(sp_path) if sp_path.exists() else ""
    sp_tokens = count_tokens(encoder, security_prompt) if security_prompt else 0

    include_globs = DEFAULT_INCLUDE_GLOBS + args.include
    exclude_globs = DEFAULT_EXCLUDE_GLOBS + args.exclude
    exclude_dirs = list(DEFAULT_EXCLUDE_DIRS.union(set(args.exclude_dir)))

    files = collect_files(
        repo, include_globs, exclude_globs, exclude_dirs,
        args.max_file_bytes, args.min_file_bytes, log_skipped=args.log_skipped
    )

    # Header/footer sizes
    dummy_header = PART_HEADER_TEMPLATE.format(i=1, n=1)
    dummy_footer = END_FOOTER_TEMPLATE.format(i=1, n=1)
    header_tokens = count_tokens(encoder, dummy_header)
    footer_tokens = count_tokens(encoder, dummy_footer)

    # Budgets (depending on embed mode)
    if args.embed_security_prompt == "none":
        fixed_overhead = sp_tokens + header_tokens + footer_tokens + args.reserve_completion + args.safety_margin
        if fixed_overhead >= args.model_context:
            print(
                f"[error] Insufficient budget: fixed={fixed_overhead} >= context={args.model_context}\n"
                f"- security_prompt={sp_tokens}, header={header_tokens}, footer={footer_tokens}, "
                f"reserve={args.reserve_completion}, safety={args.safety_margin}",
                file=sys.stderr,
            )
            sys.exit(2)
        per_part_limit = args.model_context - fixed_overhead

        def part_limit(idx: int) -> int:
            # same for all parts
            return per_part_limit

        def approx_total_tokens(md_tokens: int) -> int:
            return md_tokens + sp_tokens + args.reserve_completion + args.safety_margin

    elif args.embed_security_prompt == "first":
        fixed_overhead_common = header_tokens + footer_tokens + args.reserve_completion + args.safety_margin
        if fixed_overhead_common + sp_tokens >= args.model_context:
            print(
                f"[error] Insufficient budget: header+footer+reserve+safety+SP="
                f"{fixed_overhead_common + sp_tokens} >= context={args.model_context}",
                file=sys.stderr,
            )
            sys.exit(2)
        per_part_limit = args.model_context - fixed_overhead_common

        def part_limit(idx: int) -> int:
            # first part: minus SP inside part; others — full payload budget
            return per_part_limit - sp_tokens if idx == 1 else per_part_limit

        def approx_total_tokens(md_tokens: int) -> int:
            # SP is included inside parts (actually present in first)
            return md_tokens + args.reserve_completion + args.safety_margin

    else:  # "each"
        fixed_overhead_each = header_tokens + footer_tokens + args.reserve_completion + args.safety_margin + sp_tokens
        if fixed_overhead_each >= args.model_context:
            print(
                f"[error] Insufficient budget: header+footer+reserve+safety+SP="
                f"{fixed_overhead_each} >= context={args.model_context}",
                file=sys.stderr,
            )
            sys.exit(2)
        per_part_limit = args.model_context - fixed_overhead_each

        def part_limit(idx: int) -> int:
            return per_part_limit

        def approx_total_tokens(md_tokens: int) -> int:
            return md_tokens + args.reserve_completion + args.safety_margin + sp_tokens

    # Packing files into parts (without splitting single file)
    parts: List[List[Tuple[pathlib.Path, str, int]]] = [[]]
    part_payload_tokens: List[int] = [0]  # only payload blocks (without header/footer and SP in none mode)

    skipped_extra: List[Tuple[pathlib.Path, str]] = []

    def file_block(path: pathlib.Path, content: str) -> str:
        return FILE_BLOCK_TEMPLATE.format(path=str(path.resolve()), content=content)

    # Place one by one
    for p in files:
        text = read_text_safe(p)
        block = file_block(p, text)
        t = count_tokens(encoder, block)

        # Limit for CURRENT part
        current_index = len(parts)  # 1-based
        current_limit = part_limit(current_index)

        if t > current_limit:
            # one file > current part limit
            # try to start NEW part and check its limit
            next_limit = part_limit(current_index + 1)  # limit for potential new part
            if t > next_limit:
                # file is larger than ANY part limit
                if args.oversize_policy == "error":
                    print(
                        f"[error] Oversize file > per-part limit and cannot be split:\n"
                        f"  file: {p}\n  file_tokens: {t}\n  per_part_limit: {next_limit}\n"
                        f"  context: {args.model_context} (adjust settings or exclude file)",
                        file=sys.stderr,
                    )
                    sys.exit(3)
                elif args.oversize_policy == "skip":
                    skipped_extra.append((p, f"oversize>limit({t}>{next_limit})"))
                    if args.log_skipped:
                        print(f"[skipped] {p} (oversize>limit {t}>{next_limit})")
                    continue
                else:  # allow
                    # create OWN part only with this file, even if it exceeds final model context
                    parts.append([(p, block, t)])
                    part_payload_tokens.append(t)
                    continue
            else:
                # file will fit in new part — open new one
                parts.append([])
                part_payload_tokens.append(0)
                current_index = len(parts)
                current_limit = part_limit(current_index)

        # If doesn't fit in current (after attempt), and part already has content — open new one
        if part_payload_tokens[-1] + t > current_limit and part_payload_tokens[-1] > 0:
            parts.append([])
            part_payload_tokens.append(0)
            current_index = len(parts)
            current_limit = part_limit(current_index)

        # Now definitely add completely
        parts[-1].append((p, block, t))
        part_payload_tokens[-1] += t

    total_parts = len(parts)

    # Writing parts
    for idx, part in enumerate(parts, start=1):
        header = PART_HEADER_TEMPLATE.format(i=idx, n=total_parts)
        body = ""

        if args.embed_security_prompt == "first" and idx == 1 and security_prompt:
            body += security_prompt + "\n\n"
        elif args.embed_security_prompt == "each" and security_prompt:
            body += security_prompt + "\n\n"

        body += "".join(block for _, block, _ in part)
        footer = END_FOOTER_TEMPLATE.format(i=idx, n=total_parts)
        md = header + body + footer

        out_file = outdir / f"prompt_part_{idx:03d}.md"
        out_file.write_text(md, encoding="utf-8")

        approx = approx_total_tokens(count_tokens(encoder, md))
        warn = " [!! exceeds model context]" if approx > args.model_context else ""
        print(f"[+] wrote {out_file}  (≈{approx}/{args.model_context} tokens incl. reserves){warn}")

    if args.log_skipped and skipped_extra:
        for p, why in skipped_extra:
            print(f"[skipped] {p} ({why})")

    # Summary
    print("\nSummary:")
    print(f"- embed_security_prompt: {args.embed_security_prompt}")
    print(f"- oversize_policy: {args.oversize_policy}")
    print(f"- security_prompt_tokens: {sp_tokens}")
    print(f"- header_tokens: {header_tokens}, footer_tokens: {footer_tokens}")
    print(f"- reserve_completion: {args.reserve_completion}, safety_margin: {args.safety_margin}")
    print(f"- per_part_limit (payload-only): {part_limit(1)} (first part)")

if __name__ == "__main__":
    main()
