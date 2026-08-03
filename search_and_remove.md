# Remove `addShortText` Calls — Automation Script

A Python script that scans repositories in a GitHub Enterprise organization,
finds calls to the deprecated `addShortText` function in specific Groovy
Jenkinsfiles located in the root directory of each repository, removes those
lines, and automatically creates a Pull Request for each affected repository —
all directly via the GitHub API without cloning repositories locally.

> **Primary use case:** remove all calls to the deprecated `addShortText`
> function across 300+ repositories in the `Portal-CF` GitHub Enterprise
> organization.
>
> **General use case:** the script can be adapted to find and remove (or
> replace) any pattern across a fixed set of files in multiple repositories —
> simply update the `SEARCH_PATTERN`, `REPLACE_WITH`, and `TARGET_FILES`
> fields in the Configuration section.

---

## Requirements

- Python 3.x
- PyGithub library
- Personal Access Token for GitHub Enterprise

---

## Installation

### 1. Download the script

```bash
cd ~/git/remove-addShortText
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
at the top of `search_and_remove.py`:

```python
GITHUB_URL      = "https://github.wdf.sap.corp"          # GitHub Enterprise URL
GITHUB_TOKEN    = os.environ.get("GITHUB_TOKEN")          # reads from environment
ORG_NAME        = "Portal-CF"                             # target organization
BRANCH_NAME     = "remove-addShortText"                   # new branch name
COMMIT_MESSAGE  = "remove-addShortText"                   # commit message
PR_TITLE        = "CUSTOM:remove-addShortText"            # pull request title
PR_BODY         = "remove the call to the deprecated addShortText function"

SEARCH_PATTERN  = re.compile(r"^[^\S\r\n]*addShortText\s*\(.*\)\s*$", re.MULTILINE)
REPLACE_WITH    = ""                                      # line is removed entirely

TARGET_FILES    = {
    "CumulusCIJenkinsFile",
    "JenkinsfileSecurityScanCI",
    "JenkinsfileSecurityScanCTP",
    "JenkinsfileSecurityScanOOEM",
}
```

> To adapt the script for a different pattern — update `SEARCH_PATTERN`,
> `REPLACE_WITH`, and `TARGET_FILES`.

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

> **Tip:** use `REPOSITORY_LIST` together with `--dry-run` first
> to verify the script finds the correct lines before touching anything.

---

## Run Modes

The script supports two run modes selected via a command-line flag.

### Normal mode — scan and apply changes

Runs both steps: scans all repositories, then creates branches and Pull
Requests after a manual confirmation prompt.

```bash
python3 search_and_remove.py
```

### Dry-run mode — scan only, no changes

Runs **Step 1 only**: scans all repositories and produces a full report,
then exits immediately **without** creating any branches, commits, or Pull
Requests. The GitHub API is used in read-only mode.

```bash
python3 search_and_remove.py --dry-run
```

Use dry-run mode to:
- verify that the script finds the correct repositories and lines
- review the scope of changes before committing to them
- share the scan report with your team for sign-off

> Dry-run and normal-mode log files are saved with different name prefixes
> (`dry_run_` vs `apply_`) so they never overwrite each other.

---

## How to Run

### Recommended workflow

**Step 1 — run a dry-run first:**

```bash
cd ~/git/remove-addShortText
source .venv/bin/activate
python3 search_and_remove.py --dry-run
```

Review the log file in the `logs/` folder.
Verify that the affected repositories and line numbers look correct.

**Step 2 — run for real:**

```bash
python3 search_and_remove.py
```

Review the scan results in the console, then press Enter to create branches
and Pull Requests.

---

## How It Works

The script runs in two steps with a manual confirmation pause between them.
In `--dry-run` mode only Step 1 is executed.

### Step 1 — Scan

1. Connects to the GitHub Enterprise instance
2. Determines repositories to scan based on `REPOSITORY_LIST`:
    - if not empty — fetches only the listed repositories
    - if empty — fetches all repositories in the organization
3. For each repository scans only the default branch (`master` or `main`)
4. Checks **only** the following files in the **root directory** of each repository:
    - `CumulusCIJenkinsFile`
    - `JenkinsfileSecurityScanCI`
    - `JenkinsfileSecurityScanCTP`
    - `JenkinsfileSecurityScanOOEM`
5. If a file does not exist in a repository — silently skips it (404 is not an error)
6. Searches each file for lines containing an `addShortText(...)` call and records the line numbers
7. Builds a sorted (A→Z) list of affected repositories and files
8. Prints the results to the console and saves them to a log file
9. If a file cannot be read for reasons other than 404 — logs the error and continues
10. **In `--dry-run` mode:** exits here — no changes are made
11. **In normal mode:** pauses and waits for your confirmation before making any changes

### Step 2 — Apply changes (after pressing Enter, normal mode only)

For each affected repository:

1. Checks if a Pull Request for `BRANCH_NAME` already exists:
    - if yes — logs `[SKIPPED]` with the existing PR URL and moves on
    - if no — proceeds with the changes
2. Creates a new branch `remove-addShortText` on GitHub
3. For each affected file: removes every line that contains an `addShortText(...)` call
4. Pushes all file changes as a **single commit** via the GitHub Git Tree API
5. Creates a **Pull Request** against the default branch
6. Logs the Pull Request URL
7. If any error occurs — logs the error and continues with the next repository

> No files are downloaded to your local machine —
> all operations are performed directly via the GitHub API.

---

## What Exactly Gets Removed

The script removes any line that matches the following regular expression:

```
^[^\S\r\n]*addShortText\s*\(.*\)\s*$
```

This means: the **entire line** is removed (including its indentation) if it
contains an `addShortText(...)` call — regardless of the arguments passed to
the function or the amount of leading whitespace.

**Example — before:**

```groovy
pipeline {
    agent any
    stages {
        stage('Build') {
            steps {
                addShortText(text: 'build-123', color: 'blue')
                sh 'make build'
            }
        }
    }
}
```

**Example — after:**

```groovy
pipeline {
    agent any
    stages {
        stage('Build') {
            steps {
                sh 'make build'
            }
        }
    }
}
```

---

## Error Handling

The script is designed to be resilient — errors do not stop execution:

| Situation | Behavior |
|-----------|----------|
| Repository cannot be fetched | Logs `[ERROR]` and skips to next repository |
| Target file not found in repository (404) | Silently skipped — this is expected |
| File cannot be read (non-404 error) | Logs `[ERROR]` and skips to next file |
| Regex produces no changes in a file | Logs `[WARN]` and skips to next file |
| File cannot be edited during PR step | Logs `[ERROR]` and skips to next file |
| All file edits failed in a repository | Logs `[SKIPPED]` and skips commit and PR |
| PR creation or commit fails | Logs `[ERROR]` and skips to next repository |
| Pull Request already exists | Logs `[SKIPPED]` with existing PR URL and moves on |

> If the script is interrupted — simply run it again.
> Already created Pull Requests will be detected and skipped automatically.

---

## Expected Output

### Dry-run mode

```bash
python3 search_and_remove.py --dry-run
```

```
============================================================
Scanning organization : Portal-CF
Mode                  : DRY RUN — no branches or PRs will be created
Date                  : 2025-01-15 10:42:00
============================================================

Scan mode: FULL ORG scan

Total repositories to scan: 312

[1/312] Scanning: another-repo (master) ... not found
[2/312] Scanning: ci-demo (master) ... FOUND in 2 file(s)
[3/312] Scanning: hello-dummy-devops (main) ... not found
[4/312] Scanning: portal-cf-lep-service (master) ... FOUND in 1 file(s)
...

============================================================
SCAN RESULTS — repositories containing addShortText calls
Repositories found: 2
============================================================

[REPO] ci-demo
   [FILE] CumulusCIJenkinsFile          (lines: 14)
   [FILE] JenkinsfileSecurityScanCI     (lines: 22, 31)

[REPO] portal-cf-lep-service
   [FILE] JenkinsfileSecurityScanCTP    (lines: 9)

============================================================
Log saved to: ./logs/remove_addShortText_dry_run_20250115_104200.log

DRY RUN complete — no branches or Pull Requests were created.
============================================================
```

### Normal mode — console output during scan

```bash
python3 search_and_remove.py
```

```
============================================================
Scanning organization : Portal-CF
Mode                  : APPLY — branches and PRs will be created
Date                  : 2025-01-15 10:45:00
============================================================

Scan mode: FULL ORG scan

Total repositories to scan: 312

[1/312] Scanning: another-repo (master) ... not found
[2/312] Scanning: ci-demo (master) ... FOUND in 2 file(s)
...

============================================================
SCAN RESULTS — repositories containing addShortText calls
Repositories found: 2
============================================================

[REPO] ci-demo
   [FILE] CumulusCIJenkinsFile          (lines: 14)
   [FILE] JenkinsfileSecurityScanCI     (lines: 22, 31)

[REPO] portal-cf-lep-service
   [FILE] JenkinsfileSecurityScanCTP    (lines: 9)

============================================================
Log saved to: ./logs/remove_addShortText_apply_20250115_104500.log

> Press Enter to start creating branches and PRs on GitHub...
```

### Normal mode — console output after pressing Enter

```
============================================================
CREATING BRANCHES AND PULL REQUESTS
============================================================

──────────────────────────────────────────────────
[REPO] ci-demo
   [OK] Branch created on GitHub: remove-addShortText
   [EDITED] CumulusCIJenkinsFile         (lines removed: 14)
   [EDITED] JenkinsfileSecurityScanCI    (lines removed: 22, 31)
   [OK] Single commit for all files: 'remove-addShortText'
   [PR] https://github.wdf.sap.corp/Portal-CF/ci-demo/pull/57

──────────────────────────────────────────────────
[REPO] portal-cf-lep-service
   [SKIPPED] Pull Request already exists: https://github.wdf.sap.corp/Portal-CF/portal-cf-lep-service/pull/23

============================================================
All done!
============================================================
```

### Log files

Log files are automatically created in the `logs/` subfolder:

| Mode | Log filename example |
|------|----------------------|
| Dry-run | `logs/remove_addShortText_dry_run_20250115_104200.log` |
| Normal | `logs/remove_addShortText_apply_20250115_104500.log` |

---

## Next Steps After the Script Completes

1. Open the log file in the `logs/` folder
2. Find all `[PR]` lines and copy the Pull Request URLs
3. Open each Pull Request in your browser
4. Review the changes manually — verify that only `addShortText` lines were removed
5. Merge the Pull Request if the changes look correct

> Pull Requests are created **without auto-merge** intentionally —
> all changes must be reviewed and merged manually.
