#!/usr/bin/env python3.12
"""
Pancake: Directory Flattener for Claude Projects

This script takes a directory and flattens its structure for easy uploading to Claude,
preserving path information in the filenames and adding context files for structure.
"""

import os
import sys
import shutil
import argparse
import platform
import subprocess
import hashlib
import time
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional
import re
from fnmatch import fnmatch
from tqdm import tqdm


class Pancake:
    def __init__(self,
                 source_dir: str,
                 output_dir: str,
                 exclude_patterns: List[str] = None,
                 max_file_size_kb: int = 1024,
                 include_binary: bool = False,
                 separator: str = "_",
                 use_gitignore: bool = True):
        self.source_dir = os.path.abspath(source_dir)
        self.output_dir = os.path.abspath(output_dir)

        # Base exclude patterns
        self.exclude_patterns = exclude_patterns or []
        self.default_exclude_patterns = [".git", "__pycache__", "node_modules", ".DS_Store", "*.pyc", "venv", ".venv",
                                         "env", ".env", ".idea"]

        # Add output directory to excludes to prevent recursive flattening
        output_dir_name = os.path.basename(self.output_dir)
        if output_dir_name:
            self.default_exclude_patterns.append(output_dir_name)
            # Also exclude common variations
            self.default_exclude_patterns.append("pancaked")
            self.default_exclude_patterns.append("pancake_output")

        # Add gitignore patterns if requested
        self.gitignore_patterns = []
        if use_gitignore:
            self.gitignore_patterns = self.parse_gitignore()

        # Combine all exclude patterns
        self.all_patterns = self.default_exclude_patterns + self.exclude_patterns + self.gitignore_patterns

        # Process exclude patterns to identify directory patterns for early skipping
        self.dir_exclude_patterns = []
        for pattern in self.all_patterns:
            # Remove trailing wildcards for directory checks
            dir_pattern = pattern.rstrip('/*')
            if dir_pattern:
                self.dir_exclude_patterns.append(dir_pattern)

        self.max_file_size_kb = max_file_size_kb
        self.include_binary = include_binary
        self.separator = separator
        self.collision_count = 0
        self.skipped_files: List[Tuple[str, str]] = []  # (path, reason)
        self.skipped_dirs: List[Tuple[str, str]] = []  # (path, reason)

        # Timing information
        self.start_time = 0
        self.end_time = 0

    def is_binary_file(self, file_path: str) -> bool:
        """Check if a file is binary by reading the first chunk and looking for null bytes."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                f.read(1024)
                return False
        except UnicodeDecodeError:
            return True

    def parse_gitignore(self) -> List[str]:
        """Parse .gitignore files and return patterns to exclude."""
        gitignore_patterns = []
        gitignore_locations = [
            # Project root .gitignore
            os.path.join(self.source_dir, '.gitignore'),
            # JetBrains specific locations
            os.path.join(self.source_dir, '.idea', '.gitignore')
        ]

        found_gitignore = False
        for gitignore_path in gitignore_locations:
            if os.path.exists(gitignore_path):
                found_gitignore = True
                print(f"Found .gitignore at: {gitignore_path}")
                try:
                    with open(gitignore_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            # Skip empty lines and comments
                            if line and not line.startswith('#'):
                                # Handle negation (!)
                                if line.startswith('!'):
                                    continue  # Skip negation for simplicity
                                # Handle directory-specific patterns (ending with /)
                                if line.endswith('/'):
                                    line = line[:-1]  # Remove trailing slash
                                gitignore_patterns.append(line)
                except Exception as e:
                    print(f"Error reading gitignore: {e}")

        if found_gitignore:
            print(f"Using gitignore to skip untracked files (found {len(gitignore_patterns)} patterns)")
        else:
            print("Using default ignore list (no .gitignore found)")

        return gitignore_patterns

    def matches_pattern(self, path: str, pattern: str) -> bool:
        """Check if a path matches a pattern, handling gitignore-style patterns."""
        rel_path = os.path.relpath(path, self.source_dir)

        # Handle directory wildcards with **
        if '**' in pattern:
            parts = pattern.split('**')
            if len(parts) == 2:
                start, end = parts
                if not start or rel_path.startswith(start):
                    if not end or rel_path.endswith(end):
                        return True

        # Handle single asterisk wildcards
        if '*' in pattern:
            return fnmatch(rel_path, pattern)

        # Handle directory-specific matching
        if os.path.isdir(path) and pattern.endswith('/'):
            return rel_path == pattern[:-1] or rel_path.startswith(pattern)

        # Direct matching
        return rel_path == pattern or pattern in rel_path

    def should_exclude_dir(self, dir_path: str) -> Tuple[bool, str]:
        """Check if a directory should be excluded. This is used for early pruning."""
        rel_path = os.path.relpath(dir_path, self.source_dir)

        # Check if this directory is in the exclude list or a subdirectory of an excluded dir
        for pattern in self.dir_exclude_patterns:
            if rel_path == pattern or rel_path.startswith(pattern + os.path.sep):
                return True, f"Matched directory pattern {pattern}"

        # Also check full patterns (for more complex directory exclusions)
        for pattern in self.all_patterns:
            if self.matches_pattern(dir_path, pattern):
                return True, f"Matched pattern {pattern}"

        return False, ""

    def should_exclude(self, path: str) -> Tuple[bool, str]:
        """Check if a path should be excluded based on patterns or file characteristics."""
        rel_path = os.path.relpath(path, self.source_dir)

        # Direct directory exclusion - check if the path is in or under any excluded directory
        for pattern in self.dir_exclude_patterns:
            # Check if this path is in the excluded directory or a subdirectory of it
            if rel_path == pattern or rel_path.startswith(pattern + os.path.sep):
                return True, f"Matched directory pattern {pattern}"

        # Also check normal pattern matching
        for pattern in self.all_patterns:
            if self.matches_pattern(path, pattern):
                return True, f"Matched pattern {pattern}"

        # Check if it's a file
        if os.path.isfile(path):
            # Check file size
            size_kb = os.path.getsize(path) / 1024
            if size_kb > self.max_file_size_kb:
                return True, f"File too large ({size_kb:.1f} KB > {self.max_file_size_kb} KB)"

            # Check if binary
            if not self.include_binary and self.is_binary_file(path):
                return True, "Binary file (use --include-binary to include)"

        return False, ""

    def flatten_name(self, path: str) -> str:
        """Convert a path to a flattened filename, preserving structure in the name."""
        rel_path = os.path.relpath(path, self.source_dir)
        # Replace path separators with the chosen separator
        flat_name = rel_path.replace(os.path.sep, self.separator)
        # Handle special characters that might be problematic in filenames
        flat_name = re.sub(r'[<>:"|?*]', '_', flat_name)
        return flat_name

    def resolve_collision(self, filename: str) -> str:
        """Handle filename collisions by adding a short hash."""
        base, ext = os.path.splitext(filename)
        hash_val = hashlib.md5(filename.encode()).hexdigest()[:6]
        self.collision_count += 1
        return f"{base}_{hash_val}{ext}"

    def generate_tree(self) -> str:
        """Generate a tree representation of the directory structure."""
        try:
            # Using the 'tree' command (we assume it's installed)
            exclude_patterns = '|'.join(p.replace(' ', r'\ ') for p in self.all_patterns if not p.startswith('*'))
            cmd = ['tree', '-a']

            if exclude_patterns:
                cmd.extend(['-I', exclude_patterns])

            cmd.append(self.source_dir)

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout

            # If tree command fails, provide error and installation instructions
            return (f"Error running tree command: {result.stderr}\n\n"
                    f"Please install the 'tree' command:\n"
                    f"- On Ubuntu/Debian: sudo apt-get install tree\n"
                    f"- On MacOS: brew install tree\n"
                    f"- On Windows: Install via Chocolatey: choco install tree\n\n"
                    f"Simple directory listing (as fallback):\n{os.listdir(self.source_dir)}")

        except Exception as e:
            return f"Error generating tree: {e}\n\nSimple directory listing:\n{os.listdir(self.source_dir)}"

    def count_files_to_process(self) -> int:
        """Count the total number of files that will be processed for progress bar."""
        count = 0
        for root, dirs, files in os.walk(self.source_dir):
            # Early pruning - filter out excluded directories
            dirs[:] = [d for d in dirs if not self.should_exclude_dir(os.path.join(root, d))[0]]

            # Count files that won't be excluded
            for file in files:
                file_path = os.path.join(root, file)
                if not self.should_exclude(file_path)[0]:
                    count += 1
        return count

    def generate_context(self) -> str:
        """Generate a context file with relevant system and project information."""
        # Calculate time taken
        time_taken = self.end_time - self.start_time
        hours, remainder = divmod(time_taken, 3600)
        minutes, seconds = divmod(remainder, 60)
        time_str = ""
        if hours > 0:
            time_str += f"{int(hours)}h "
        if minutes > 0:
            time_str += f"{int(minutes)}m "
        time_str += f"{seconds:.1f}s"

        context = [
            "# Project Context Information",
            "",
            f"Generated by Pancake on {platform.node()}",
            "",
            "## System Information",
            f"- OS: {platform.system()} {platform.release()}",
            f"- Python: {platform.python_version()}",
            "",
            "## Project Information",
            f"- Source Directory: {self.source_dir}",
            f"- Files Processed: {len(os.listdir(self.output_dir)) - 3}",  # Exclude tree, context, and excluded files
            f"- Files Skipped: {len(self.skipped_files)}",
            f"- Directories Skipped: {len(self.skipped_dirs)}",
            f"- Filename Collisions Resolved: {self.collision_count}",
            f"- Processing Time: {time_str}",
            "",
            "## Note",
            "- Detailed exclusion information and skipped files are available in 00_pancake_excluded.md",
            "",
        ]

        return '\n'.join(context)

    def generate_excluded_info(self) -> str:
        """Generate a file with detailed information about excluded patterns and skipped files."""
        excluded_info = [
            "# Pancake Exclusion Information",
            "",
            f"Generated by Pancake for project at {self.source_dir}",
            "",
            "## Exclusion Patterns",
            f"- Default Patterns: {', '.join(self.default_exclude_patterns)}",
            f"- GitIgnore Patterns: {len(self.gitignore_patterns)} patterns found",
        ]

        if self.gitignore_patterns:
            excluded_info.extend([
                "",
                "### GitIgnore Patterns",
                ""
            ])
            for pattern in self.gitignore_patterns:
                excluded_info.append(f"- `{pattern}`")

        excluded_info.extend([
            "",
            f"- Custom Exclude Patterns: {', '.join(self.exclude_patterns) if self.exclude_patterns else 'None'}",
            "",
        ])

        if self.skipped_dirs:
            excluded_info.extend([
                "## Skipped Directories",
                ""
            ])
            for path, reason in self.skipped_dirs:
                rel_path = os.path.relpath(path, self.source_dir)
                excluded_info.append(f"- `{rel_path}/`: {reason}")
            excluded_info.append("")

        if self.skipped_files:
            excluded_info.extend([
                "## Skipped Files",
                ""
            ])
            # Group skipped files by reason to make the output more compact
            reason_groups = {}
            for path, reason in self.skipped_files:
                if reason not in reason_groups:
                    reason_groups[reason] = []
                rel_path = os.path.relpath(path, self.source_dir)
                reason_groups[reason].append(rel_path)

            for reason, paths in reason_groups.items():
                excluded_info.append(f"### {reason}")
                excluded_info.append("")
                # Limit to first 100 files if there are too many
                if len(paths) > 100:
                    for path in paths[:100]:
                        excluded_info.append(f"- `{path}`")
                    excluded_info.append(f"- ... and {len(paths) - 100} more files")
                else:
                    for path in paths:
                        excluded_info.append(f"- `{path}`")
                excluded_info.append("")

        return '\n'.join(excluded_info)

    def process(self) -> None:
        """Process the source directory and create the flattened output."""
        self.start_time = time.time()

        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)

        # Count files to process for progress bar
        print("Scanning directory to count files...")
        total_files = self.count_files_to_process()
        print(f"Found {total_files} files to process")

        # Track filenames to handle collisions
        used_filenames: Set[str] = set()

        # Set up progress bar
        pbar = tqdm(total=total_files, desc="Processing files", unit="file")

        # Walk the directory tree
        for root, dirs, files in os.walk(self.source_dir):
            # Early pruning - filter out excluded directories
            for d in list(dirs):  # Make a copy of dirs so we can modify it while iterating
                dir_path = os.path.join(root, d)
                should_exclude, reason = self.should_exclude_dir(dir_path)
                if should_exclude:
                    self.skipped_dirs.append((dir_path, reason))
                    dirs.remove(d)  # This will prevent os.walk from descending into this directory

            # Process each file
            for file in files:
                file_path = os.path.join(root, file)

                # Check if file should be excluded
                should_exclude, reason = self.should_exclude(file_path)
                if should_exclude:
                    self.skipped_files.append((file_path, reason))
                    continue

                # Generate flattened filename
                flat_name = self.flatten_name(file_path)

                # Handle collisions
                if flat_name in used_filenames:
                    flat_name = self.resolve_collision(flat_name)

                used_filenames.add(flat_name)

                # Copy file to output directory
                shutil.copy2(file_path, os.path.join(self.output_dir, flat_name))

                # Update progress bar
                pbar.update(1)

        # Close progress bar
        pbar.close()

        # Record end time
        self.end_time = time.time()

        print("Generating directory structure...")
        # Generate and save the tree structure
        tree_content = self.generate_tree()
        with open(os.path.join(self.output_dir, "00_directory_structure.txt"), 'w', encoding='utf-8') as f:
            f.write(tree_content)

        print("Generating context files...")
        # Generate and save the context information (smaller version)
        context_content = self.generate_context()
        with open(os.path.join(self.output_dir, "00_project_context.md"), 'w', encoding='utf-8') as f:
            f.write(context_content)

        # Generate and save the excluded files information
        excluded_content = self.generate_excluded_info()
        with open(os.path.join(self.output_dir, "00_pancake_excluded.md"), 'w', encoding='utf-8') as f:
            f.write(excluded_content)

        # Calculate time taken
        time_taken = self.end_time - self.start_time
        hours, remainder = divmod(time_taken, 3600)
        minutes, seconds = divmod(remainder, 60)
        time_str = ""
        if hours > 0:
            time_str += f"{int(hours)}h "
        if minutes > 0:
            time_str += f"{int(minutes)}m "
        time_str += f"{seconds:.1f}s"

        print(f"Directory structure flattened successfully to {self.output_dir}")
        print(f"Processed: {len(used_filenames)} files")
        print(f"Skipped: {len(self.skipped_files)} files in {len(self.skipped_dirs)} directories")
        print(f"Filename collisions resolved: {self.collision_count}")
        print(f"Total time: {time_str}")


def main():
    parser = argparse.ArgumentParser(description='Flatten directory structure for easier uploading to Claude.')
    parser.add_argument('source_dir', help='Source directory to flatten')
    parser.add_argument('--output-dir', '-o', default=None,
                        help='Output directory (defaults to "pancaked" folder in the source directory)')
    parser.add_argument('--exclude', '-e', action='append',
                        help='Additional patterns to exclude (can be used multiple times)')
    parser.add_argument('--max-size', '-m', type=int, default=1024,
                        help='Maximum file size in KB (default: 1024)')
    parser.add_argument('--include-binary', '-b', action='store_true',
                        help='Include binary files')
    parser.add_argument('--separator', '-s', default='_',
                        help='Separator for path components in filenames (default: _)')
    parser.add_argument('--no-gitignore', action='store_true',
                        help='Ignore .gitignore files when determining what to exclude')

    args = parser.parse_args()

    # Set default output directory to be "pancaked" folder in the source directory
    output_dir = args.output_dir
    if output_dir is None:
        output_dir = os.path.join(args.source_dir, "pancaked")

    exclude_patterns = []
    if args.exclude:
        exclude_patterns.extend(args.exclude)

    pancake = Pancake(
        source_dir=args.source_dir,
        output_dir=output_dir,
        exclude_patterns=exclude_patterns,
        max_file_size_kb=args.max_size,
        include_binary=args.include_binary,
        separator=args.separator,
        use_gitignore=not args.no_gitignore
    )

    pancake.process()


if __name__ == "__main__":
    main()
