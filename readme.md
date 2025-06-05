# Pancake 🥞

**Directory flattener for Claude projects**

Pancake is a utility that flattens a directory structure for easy uploading to Claude chat projects. It preserves path information in filenames, respects gitignore files, and adds context about the project structure.

## The Problem

When working with Claude's project feature, uploading an entire project directory structure can be challenging:
- Files are scattered across many nested directories
- The conversation hits token limits quickly 
- You need to manually provide directory context
- Re-uploading after changes is time-consuming

## The Solution

Pancake "flattens" your directory structure into a single folder where:
- Original file paths are preserved in the filenames (e.g., `src/engine/main.py` becomes `src_engine_main.py`)
- A directory structure visualization is included
- Context information is automatically generated
- gitignore rules are respected to avoid irrelevant files

## Features

- 📁 Transforms nested directory structures into flat file collections
- 🌲 Includes a tree-view representation of the original structure
- 🔍 Respects `.gitignore` patterns to exclude untracked/generated files
- ⚙️ Auto-excludes virtual environments, IDE files, and binary files
- 🛠️ Handles filename collisions with intelligent hashing
- 📊 Provides detailed context information about the project

## Installation

```bash
# Make the script executable and install
./deploy.sh

# Or manually:
chmod +x pancake.py
cp pancake.py ~/bin/pancake
```

## Usage

```bash
# Basic usage (creates a "pancaked" folder in your project)
pancake /path/to/your/project

# Specify custom output location
pancake /path/to/your/project -o /path/to/output

# Include binary files
pancake /path/to/your/project --include-binary

# Ignore gitignore files
pancake /path/to/your/project --no-gitignore

# Add custom excludes
pancake /path/to/your/project --exclude "*.log" --exclude "build/*"
```

## How to Use with Claude

1. Run pancake on your project directory
2. Select all files from the generated "pancaked" folder
3. Drag and drop them into a Claude chat
4. The directory structure and context files provide Claude with project information
5. When you make changes to your project, run pancake again and re-upload

## Requirements

- Python 3.12
- `tree` command (installed on most Unix systems)
  - Ubuntu/Debian: `sudo apt-get install tree`
  - macOS: `brew install tree`
  - Windows: `choco install tree`
