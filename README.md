# novamind

# novamind

## GIT RULES AND MANDATORY PRACTICES

### NEVER DO THIS

#### DO NOT commit directly to main branch
Main branch is updated ONLY through Pull Requests. Direct commits will cause serious problems and can break the project.

#### DO NOT commit to someone else's branch
Everyone works on their own branch. Do not touch other people's code.

#### DO NOT ignore conflicts
When conflicts appear, do not panic. Stay calm and contact the Scrum Master.

#### DO NOT push without unit testing
Pushing broken code affects the entire team.

---

## MANDATORY RULES

### Rule 1: Create new branch for every task
Got a new task? Create a new branch.

**Branch name format:** `feature/yourname-what-you-are-doing`

**Examples:**
- `feature/ahmet-email-filtering`
- `feature/ayse-mobile-login`
- `bugfix/mehmet-crash-fix`

### Rule 2: Always branch from main

Always start from main branch. Update main first, then create your branch.

```bash
git checkout main
git pull origin main
git checkout -b feature/yourname-task-name
```

### Rule 3: Merge main into your branch daily
While working on your branch, pull changes from main every morning. This keeps conflicts small.

```bash
git checkout main
git pull origin main
git checkout feature/yourname-task-name
git merge main
```

### Rule 4: Open Pull Request when done
Finished coding and testing? Open a Pull Request. Team reviews it, approves it, then it goes to main.

```bash
git push origin feature/yourname-task-name
```

Then open PR on GitHub.

### Rule 5: Write meaningful commit messages
Do not write "asd", "test", "update". Write what you actually did.

**Good examples:**
- `feat: added email categorization algorithm`
- `fix: resolved login screen crash`
- `docs: updated API documentation`

**Commit format:**
```
type: short description
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`
