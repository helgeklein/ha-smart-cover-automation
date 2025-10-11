# Contribution Guidelines

GitHub is used to host code, to track issues and feature requests, as well as accept pull requests.

## Contributing

Pull requests are the best way to propose changes to the codebase.

- Fork the repo and create your branch from `main`.
- Make your changes.
- Make sure your code lints (using `scripts/lint`).
- Test your contribution (use `scripts/test`; aim to keep coverage ≥ 98%).
- Update the documentation.
- Issue that pull request!

## Bug Reporting

Report a bug by [opening a new issue](../../issues/new).

**Great bug reports** tend to have:

- A quick summary and/or background
- Steps to reproduce
  - Be specific!
  - Give sample code if you can.
- What you expected would happen
- What actually happens
- Notes (possibly including why you think this might be happening, or stuff you tried that didn't work)

## Coding Style

This repository uses [Ruff](https://docs.astral.sh/ruff/) for formatting and linting.

- Format and lint locally with:

  ```bash
  ./scripts/lint
  ```

- The linter enforces import sorting and common correctness/style rules.

## Development Environment

This integration comes with a devcontainer, easy to use with Visual Studio Code. See this
[blog post](https://helgeklein.com/blog/developing-custom-integrations-for-home-assistant-getting-started/)
for helpful information on how to get started with Home Assistant integration development.

## License

By contributing, you agree that your contributions will be licensed under its MIT License.
