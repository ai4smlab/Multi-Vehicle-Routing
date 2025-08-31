# Contributing

## PR Checklist
- Tests for new features or bug fixes
- `pytest -q` passes locally
- Docs updated (`doc/` or main README if user-facing change)

## Style
- Python 3.10+ typing
- Keep route handlers thin; move logic into services
- Prefer small, composable functions; test them in isolation

## Commits
- Use clear, imperative messages
- Reference issues when appropriate: `Fixes #123`