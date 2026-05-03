# Contributing to Libertas

Thanks for taking a look. Libertas is a personal project I (Amit) use to plan
my own trips, but I'd love feedback, bug reports, and PRs.

## Easiest ways to help

- **Try it** — [libertas-travel.onrender.com](https://libertas-travel.onrender.com).
  Email me ([aabtzu@gmail.com](mailto:aabtzu@gmail.com)) for an invite code.
- **File an issue** for bugs, confusing copy, or missing features:
  [github.com/aabtzu/libertas-travel/issues](https://github.com/aabtzu/libertas-travel/issues).
- **Open a PR** — see below.

## Local development

```bash
git clone https://github.com/aabtzu/libertas-travel.git
cd libertas-travel
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export ANTHROPIC_API_KEY=your-key   # required for AI features
export SECRET_KEY=any-string        # required for Flask sessions
./dev.sh start                      # runs on http://localhost:8080
```

Other commands:

```bash
./dev.sh bg     # start in background, logs at /tmp/libertas.log
./dev.sh stop
./dev.sh test   # pytest tests/ -x -q
```

`AUTH_DISABLED=true` is set automatically by `dev.sh`, which auto-logs you in
as user 1. To preview the real auth pages, hit `/login` or `/register`
directly — they're whitelisted in dev mode.

## Pull request guidelines

- **Read [`CLAUDE.md`](CLAUDE.md) first.** It describes the file/folder
  conventions, code-style rules (ruff), CSS color palette, SQL constants
  pattern, file-length limits (target 500, hard 800 — enforced in CI), and
  more. Most "why is this organized like that?" questions are answered there.
- **Run the checks before pushing:**

  ```bash
  ruff check . && ruff format --check .
  python3 scripts/check_file_size.py
  pytest tests/ -m "not integration" -q
  ```

  CI runs all three — see `.github/workflows/test.yml`.
- **One feature/fix per PR.** Smaller is faster to review.
- **Add a test if you can.** Patterns live in `tests/`. The test suite uses
  pytest with a Flask test client; conftest.py handles fixtures.

## Things that need help

If you want a starting point, see [open issues](https://github.com/aabtzu/libertas-travel/issues).
A few I'd particularly welcome help on:

- **Mobile responsive polish** — the create-page editor and explore chat are
  not great on phones.
- **Better venue data** — `data/venues_seed.csv` is a starting set; richer
  curation would meaningfully improve recommendations.
- **Onboarding flow** — first-time users still see a bit much at once.
  Suggestions / mockups welcome.

## Be Nice

## License

MIT — see [`LICENSE`](LICENSE).
