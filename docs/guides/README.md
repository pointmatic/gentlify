# Guides Directory

This directory contains documentation for LLM-assisted development workflows and developer reference materials.

## LLM-Focused Guides

These guides provide structured instructions for LLMs to follow when working on projects:

- **`project_guide.md`** - Core workflow for LLM-assisted project creation from scratch. Read this at the start of every new project session.
- **`best_practices_guide.md`** - Diagnostic patterns and anti-patterns for evaluating project quality. Use for occasional audits.
- **`debug_guide.md`** - Test-driven debugging methodology for fixing bugs in existing projects.
- **`documentation-setup-guide.md`** - Step-by-step workflow for setting up GitHub Pages documentation with MkDocs and custom landing pages.

## Developer-Focused Guides

The `developer/` subdirectory contains manual setup instructions and troubleshooting guides for human developers:

- Manual service configuration (e.g., Codecov, PyPI trusted publishers)
- Troubleshooting references
- One-time setup procedures
- Production mode workflow and GitHub repository setup

These guides are primarily for manual setup tasks, but LLMs may reference excerpts when providing step-by-step instructions or documenting procedures in stories.

## Usage

**For LLMs:**
- Consult `project_guide.md` at the start of every project session
- Reference `debug_guide.md` when bugs are reported
- Use `documentation-setup-guide.md` when setting up public documentation
- Check `best_practices_guide.md` when auditing project quality

**For Developers:**
- Refer to `developer/` guides for manual setup tasks
- Use these guides as troubleshooting references
