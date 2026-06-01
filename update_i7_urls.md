
# GitHub URL Replace & PR Automation Script

A Python script that scans repositories in a GitHub organization,
finds occurrences of an outdated URL string, replaces it with a new one,
and automatically creates a Pull Request for each affected repository —
all directly via the GitHub API without cloning repositories locally.

> **Primary use case:** replace outdated SAP internal i7 URL references
> (`https://i7p.wdf.sap.corp`) across 300+ repositories in a GitHub
> Enterprise organization.
>
> **General use case:** the script can be used to find and replace
> any URL or string across multiple repositories — simply update
> the `OLD_URL` and `NEW_URL` fields in the Configuration section.

---

## Requirements

- Python 3.x
- PyGithub library
- Personal Access Token for GitHub Enterprise

---

## Installation

### 1. Download the script

```bash
cd ~/git/update-i7-url
```

### 2. Set up Python virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install PyGithub
```

### 3. Create a Personal Access Token

Go to your GitHub Enterprise instance:

```
Settings → Developer settings → Personal access tokens → Tokens (classic)
```

Generate a new token with the following scopes:
- `repo` — full control of private repositories
- `read:org` — read organization members and repos

### 4. Export the token as an environment variable

```bash
export GITHUB_TOKEN="your_personal_access_token"
```

> **Note:** add this line to your `~/.zshrc` or `~/.bash_profile`
> to avoid re-entering it every session.

---

## Configuration

Before running the script, review and edit the **Configuration** section
at the top of `update_i7_urls.py`:

```python
GITHUB_URL      = "https://github.wdf.sap.corp"   # GitHub Enterprise URL
GITHUB_TOKEN    = os.environ.get("GITHUB_TOKEN")   # reads from environment
ORG_NAME        = "Portal-CF"                      # target organization
OLD_URL         = "https://i7p.wdf.sap.corp"       # string to find
NEW_URL         = "https://i7p.bss.net.sap"        # replacement string
BRANCH_NAME     = "BLDXWZ-2501-fix-i7-url"         # new branch name
COMMIT_MESSAGE  = "Update URL for i7"              # commit message
PR_TITLE        = "[BLDXWZ-2501]-fix-i7-url"       # pull request title
PR_BODY         = "Replaces `https://i7p.wdf.sap.corp` → `https://i7p.bss.net.sap`"
SCAN_EXTENSIONS = {".json", ".yml", ".yaml", ".groovy", ".md"}  # file types to scan
```

> To use this script for a different URL or string replacement —
> simply change `OLD_URL`, `NEW_URL` and adjust `SCAN_EXTENSIONS` if needed.

---

## Scan Mode: full org vs. specific repositories

The script supports two scan modes controlled by the `REPOSITORY_LIST`
parameter in the Configuration section.

### Scan the entire organization

Leave `REPOSITORY_LIST` empty — the script will scan all repositories
in the organization:

```python
REPOSITORY_LIST = []
```

### Scan a specific list of repositories

Add repository names to `REPOSITORY_LIST` — the script will scan
only those repositories:

```python
REPOSITORY_LIST = [
    "ci-demo",
    "hello-dummy-devops",
    "portal-cf-lep-service",
]
```

> **Tip:** use `REPOSITORY_LIST` with one or two repositories first
> to verify the script works correctly before running a full org scan.

---

## How to Run

```bash
cd ~/git/update-i7-url
source .venv/bin/activate
python3 update_i7_urls.py
```

---

## How It Works

The script runs in two steps with a manual confirmation pause between them.

### Step 1 — Scan

1. Connects to the GitHub Enterprise instance
2. Determines repositories to scan based on `REPOSITORY_LIST`:
   - if not empty — fetches only the listed repositories
   - if empty — fetches all repositories in the organization
3. For each repository scans only the default branch (`master` or `main`)
4. Checks only files with extensions: `.json` `.yml` `.yaml` `.groovy` `.md`
5. Searches for `OLD_URL` in each file and records the line numbers
6. Builds a sorted (A→Z) list of affected repositories and files
7. Prints the results to the console and saves them to a log file
8. If a repository or file cannot be read — logs the error and continues
9. **Pauses and waits for your confirmation** before making any changes

### Step 2 — Apply changes (after pressing Enter)

For each affected repository:

1. Checks if a Pull Request for `BRANCH_NAME` already exists:
   - if yes — logs `[SKIPPED]` with the existing PR URL and moves on
   - if no — proceeds with the changes
2. Creates a new branch `BLDXWZ-2501-fix-i7-url` on GitHub
3. Replaces all occurrences of `OLD_URL` → `NEW_URL` in affected files
4. Pushes all file changes as a **single commit** via GitHub Git Tree API
5. Creates a **Pull Request** against the default branch
6. Logs the Pull Request URL
7. If any error occurs — logs the error and continues with the next repository

> No files are downloaded to your local machine —
> all operations are performed directly via the GitHub API.

---

## Error Handling

The script is designed to be resilient — errors do not stop execution:

| Situation | Behavior |
|-----------|----------|
| Repository cannot be fetched | Logs `[ERROR]` and skips to next repository |
| File cannot be read during scan | Logs `[ERROR]` and skips to next file |
| File cannot be edited during PR step | Logs `[ERROR]` and skips to next file |
| All file edits failed in a repository | Logs `[SKIPPED]` and skips commit and PR creation |
| PR creation or commit fails | Logs `[ERROR]` and skips to next repository |
| Pull Request already exists | Logs `[SKIPPED]` with existing PR URL and moves on |

> If the script is interrupted — simply run it again.
> Already created Pull Requests will be detected and skipped automatically.

---

## Expected Output

### Console output during scan

```
Scan mode: REPOSITORY_LIST (3 repositories)

Total repositories to scan: 3

[1/3] Scanning: ci-demo (master) ... not found
[2/3] Scanning: hello-dummy-devops (master) ... FOUND in 2 file(s)
[3/3] Scanning: portal-cf-lep-service (main) ... FOUND in 1 file(s)

============================================================
SCAN RESULTS — repositories containing https://i7p.wdf.sap.corp
Repositories found: 2
============================================================

[REPO] hello-dummy-devops
   [FILE] config/settings.yml  (lines: 12, 47)
   [FILE] docs/setup.md        (lines: 3)

[REPO] portal-cf-lep-service
   [FILE] .env.yaml            (lines: 8)

> Press Enter to start creating branches and PRs on GitHub...
```

### Console output after pressing Enter

```
============================================================
CREATING BRANCHES AND PULL REQUESTS
============================================================

──────────────────────────────────────────────────
[REPO] hello-dummy-devops
   [OK] Branch created on GitHub: BLDXWZ-2501-fix-i7-url
   [EDITED] config/settings.yml  (lines: 12, 47)
   [EDITED] docs/setup.md  (lines: 3)
   [OK] Single commit for all files: 'Update URL for i7'
   [PR] https://github.wdf.sap.corp/Portal-CF/hello-dummy-devops/pull/42

──────────────────────────────────────────────────
[REPO] portal-cf-lep-service
   [SKIPPED] Pull Request already exists: https://github.wdf.sap.corp/Portal-CF/portal-cf-lep-service/pull/17

============================================================
All done!
============================================================
```

### Log file

A log file is automatically created in the `logs/` subfolder of the
directory from which the script is run:

```
./logs/update_i7_20250115_104200.log
```

The log file contains the full scan report, any errors encountered,
and a list of all created Pull Request URLs:

```
[PR] https://github.wdf.sap.corp/Portal-CF/hello-dummy-devops/pull/42
[SKIPPED] Pull Request already exists: https://github.wdf.sap.corp/Portal-CF/portal-cf-lep-service/pull/17
[ERROR] Cannot read file 'some-file.yml' in 'some-repo': 404 ...
```

---

## Next Steps After the Script Completes

1. Open the log file in the `logs/` folder
2. Find all `[PR]` lines and copy the Pull Request URLs
3. Open each Pull Request in your browser
4. Review the changes manually
5. Merge the Pull Request if the changes look correct

> Pull Requests are created **without auto-merge** intentionally —
> all changes must be reviewed and merged manually.

