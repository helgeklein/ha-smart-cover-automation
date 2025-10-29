# AGENTS.md

## Lint

- Always run lint after making changes.

## Test fixing instructions

- When asked to fix tests:
    - Only change tests, not the code they're testing.
    - If you suspect an error in code being tested, tell the user about it.

## Test coverage

- config_flow.py: 100% test coverage required by Home Assistant

## Coding style

- Add docstrings and inline comments for non-obvious code.
- Don't use magic strings or magic numbers. Use centrally defined constants, enums, or similar instead.
- Above each function definition, insert three comment lines with the function name, e.g.:
  ```
  #
  # function_name
  #
  def function_name()
  ```
- Add a blank line for readability after the docstring in a function head. Example:
  ```
  def function_name()
  """Function description"""
                                # <<<<------- empty line
                                # <<<<------- first line of code
  ```

## Documentation

- Update documentation files intended for humans only when asked to. This includes:
    - Contributing.md
    - Readme.md
    - Testing.md
    - /docs/*.md

## Git Commits

- Never commit your changes. That will be done manually.