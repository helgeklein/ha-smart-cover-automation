# AGENTS.md

## Lint

- Always run lint after making changes.

## Test fixing instructions

- When asked to fix tests:
    - Only change tests, not the code they're testing.
    - If you suspect an error in code being tested, tell the user about it.

## Test

### Test coverage

- config_flow.py: 100% test coverage required by Home Assistant

### Test commands

- The script `scripts/test` always runs all tests. It's not suitable to run only individual Python test files.
- To run individual Python test files, invoke Python directly.

## Coding style

- Add docstrings and inline comments for non-obvious code.
- Don't use magic strings or magic numbers. Use centrally defined constants, enums, or similar instead.

## Documentation

- Update documentation files intended for humans only when asked to. This includes:
    - Contributing.md
    - Readme.md
    - Testing.md
    - /docs/*.md
- Don't use agent memory. Store information worth remembering as files in `/developer_docs/`.

## Git Commits

- Never commit your changes. That will be done manually.

## Python

- Don't try to create Python environments.