# Components renamed: laura-* is now basic-*

Unzip over the project, then remove the old folders (PowerShell, from the project root):

```powershell
Remove-Item -Recurse -Force components\laura-*
```

Then **Regenerate**. Nothing else to run: the database in this archive already has the new names and the
migration recorded as applied.

**About `project/project.sqlite3` in this archive:** it is your database from tiltale-v24 with one change,
514 elements renamed (`laura-decision` → `basic-decision`, and so on). If you have edited the project
since making that ZIP, do *not* unzip this file over yours; delete it from the archive first and run
`python manage.py migrate` instead: migration `0009` makes the same change to any project.

| What | Change |
|---|---|
| `components/basic-*/` (8 folders, were `laura-*`) | Folder names; `.component-basic-…` classes and `--component-basic-…` colour variables in `component.css`; the shape classes `basic-box`, `basic-arrow`, `basic-button` in CSS and SVG; display names "Basic …" in `component.json`. |
| `studio/migrations/0009_rename_laura_components.py` (new) | Renames the elements of any project that still has the old names; reversible. |
| `project/project.sqlite3`, `project/default-colors.css`, `project/style-overrides.css` | Your project: elements, colour variables and the Fonts block renamed. |
| `studio/tests.py`, `README.md`, `components/README.md` | The three literal slugs and the docs. |

Old study logs keep `"component": "laura-…"` in their `choice` events; Results labels elements from the
database, so it shows the new names. Add a changelog line for other people's projects: "run
`python manage.py migrate` after updating".
