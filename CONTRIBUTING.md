# Contributing to Elsewhere

Thank you for helping improve Elsewhere.

## Before opening an issue

- Check existing issues for the same problem.
- Run the latest release or current `main` branch.
- Remove custom content temporarily if the problem may be content-specific.
- Run `Elsewhere.exe --self-check` for a packaged build, or
  `python elsewhere.py --self-check` from source.

Bug reports should include:

- what you expected;
- what happened instead;
- steps that reliably reproduce it;
- operating system and Python version, if running from source;
- the relevant crash report or smallest useful log excerpt.

Do not upload save files or logs containing information you do not want to
make public.

## Source changes

Elsewhere supports Python 3.11 or later and intentionally uses only the
standard library at runtime.

Before submitting a pull request, run:

```text
python -W error smoke_test.py
python -W error -m ascii_battle_prototype.combat.smoke_tests
python -m ascii_battle_prototype.combat.main --validate-content
```

Keep changes focused, preserve existing save compatibility where practical,
and update player-facing documentation when behavior changes.

By contributing, you agree that your contribution may be distributed under
the project's Zero-Clause BSD License.
