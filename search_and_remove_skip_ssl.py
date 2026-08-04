import os
import re
import sys
import ssl
import urllib3
from datetime import datetime
from github import Github, InputGitTreeElement, GithubException
import requests
from requests.adapters import HTTPAdapter

# ─── Configuration ────────────────────────────────────────────────────────────
GITHUB_URL      = "https://github.wdf.sap.corp"
GITHUB_TOKEN    = os.environ.get("GITHUB_TOKEN")
ORG_NAME        = "Portal-CF"
BRANCH_NAME     = "remove-addShortText"
COMMIT_MESSAGE  = "remove-addShortText"
PR_TITLE        = "CUSTOM:remove-addShortText"
PR_BODY         = "remove the call to the deprecated addShortText function"

# Matches any line containing an addShortText(...) call
SEARCH_PATTERN  = re.compile(r"^[^\S\r\n]*addShortText\s*\(.*\)\s*$", re.MULTILINE)
REPLACE_WITH    = ""

TARGET_FILES    = {
    "CumulusCIJenkinsFile",
    "JenkinsfileSecurityScanCI",
    "JenkinsfileSecurityScanCTP",
    "JenkinsfileSecurityScanOOEM",
}

LOGS_DIR        = os.path.join(os.getcwd(), "logs")

# If repository list is not empty — scan only these repositories. Otherwise, scan the entire organization.
REPOSITORY_LIST = [
    # "ci-demo",
    # "hello-dummy-devops",
]

# ─── Parse arguments ──────────────────────────────────────────────────────────
DRY_RUN = "--dry-run" in sys.argv

# ─── SSL: disable certificate verification ────────────────────────────────────
# PyGithub uses the `requests` library internally.
# To bypass corporate self-signed certificate errors we:
#   1. Suppress urllib3 warnings about unverified HTTPS requests
#   2. Create a custom HTTPAdapter that passes verify=False at the transport level
#   3. Mount it on a requests.Session and pass that session to PyGithub

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class SSLBypassAdapter(HTTPAdapter):
    """
    An HTTPAdapter subclass that disables SSL certificate verification
    at the urllib3 level. This is the only reliable way to bypass
    self-signed certificate errors when using PyGithub, because PyGithub
    does not expose a verify=False option directly.
    """
    def send(self, request, **kwargs):
        kwargs["verify"] = False
        return super().send(request, **kwargs)

# Build a requests.Session with the SSL-bypass adapter mounted
# for the GitHub Enterprise host
session = requests.Session()
session.verify = False
session.mount("https://", SSLBypassAdapter())

# ─── Initialization ───────────────────────────────────────────────────────────
os.makedirs(LOGS_DIR, exist_ok=True)

mode_label = "dry_run" if DRY_RUN else "apply"
LOG_FILE = os.path.join(
    LOGS_DIR,
    f"remove_addShortText_{mode_label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
)

log_fh = open(LOG_FILE, "w", encoding="utf-8")

def log(msg):
    print(msg)
    log_fh.write(msg + "\n")
    log_fh.flush()

# ─── Build Github client with SSL-bypass session ──────────────────────────────
# PyGithub accepts a custom requester session via the internal
# _Github__requester attribute after construction, but the cleanest
# supported way is to monkey-patch requests.Session so that every
# instance created by PyGithub inherits verify=False.

_original_session_init = requests.Session.__init__

def _patched_session_init(self, *args, **kwargs):
    _original_session_init(self, *args, **kwargs)
    self.verify = False
    self.mount("https://", SSLBypassAdapter())

requests.Session.__init__ = _patched_session_init

g   = Github(base_url=f"{GITHUB_URL}/api/v3", login_or_token=GITHUB_TOKEN)
org = g.get_organization(ORG_NAME)


# ─── STEP 1: Scan repositories for addShortText calls ─────────────────────────
log(f"{'='*60}")
log(f"Scanning organization : {ORG_NAME}")
log(f"Mode                  : {'DRY RUN — no branches or PRs will be created' if DRY_RUN else 'APPLY — branches and PRs will be created'}")
log(f"Date                  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
log(f"{'='*60}\n")

# Build the list of repositories to scan
if REPOSITORY_LIST:
    log(f"Scan mode: REPOSITORY_LIST ({len(REPOSITORY_LIST)} repositories)\n")
    all_repos = []
    for repo_name in REPOSITORY_LIST:
        try:
            all_repos.append(org.get_repo(repo_name))
        except GithubException as e:
            log(f"[ERROR] Cannot fetch repository '{repo_name}': {e.status} — {e.data.get('message', '')}")
else:
    log(f"Scan mode: FULL ORG scan\n")
    all_repos = list(org.get_repos())

print(f"Total repositories to scan: {len(all_repos)}")

# repo_hits = { repo_name: { file_name: [line_numbers] } }
repo_hits = {}

for i, repo in enumerate(all_repos, 1):
    try:
        base_branch = repo.default_branch
        print(f"[{i}/{len(all_repos)}] Scanning: {repo.name} ({base_branch})", end=" ... ", flush=True)

        file_hits = {}

        for file_name in TARGET_FILES:
            try:
                content = repo.get_contents(file_name, ref=base_branch)
                text    = content.decoded_content.decode("utf-8", errors="replace")

                lines_with_match = [
                    lineno
                    for lineno, line in enumerate(text.splitlines(), 1)
                    if re.search(r"addShortText\s*\(", line)
                ]

                if lines_with_match:
                    file_hits[file_name] = lines_with_match

            except GithubException as e:
                if e.status == 404:
                    pass  # file simply does not exist in this repo — expected
                else:
                    log(f"\n[ERROR] Cannot read file '{file_name}' in '{repo.name}': {e.status} — {e.data.get('message', '')}")
            except Exception as e:
                log(f"\n[ERROR] Cannot read file '{file_name}' in '{repo.name}': {e}")

        if file_hits:
            repo_hits[repo.name] = file_hits
            print(f"FOUND in {len(file_hits)} file(s)")
        else:
            print("not found")

    except Exception as e:
        log(f"\n[ERROR] Cannot scan repository '{repo.name}': {e}")


# ─── Print scan results ───────────────────────────────────────────────────────
sorted_repos = sorted(repo_hits.keys())

log(f"\n{'='*60}")
log(f"SCAN RESULTS — repositories containing addShortText calls")
log(f"Repositories found: {len(sorted_repos)}")
log(f"{'='*60}")

for repo_name in sorted_repos:
    log(f"\n[REPO] {repo_name}")
    for file_name, line_numbers in sorted(repo_hits[repo_name].items()):
        lines_str = ", ".join(str(n) for n in line_numbers)
        log(f"   [FILE] {file_name}  (lines: {lines_str})")

log(f"\n{'='*60}")
log(f"Log saved to: {LOG_FILE}")


# ─── Dry-run exit point ───────────────────────────────────────────────────────
if DRY_RUN:
    log("")
    log("DRY RUN complete — no branches or Pull Requests were created.")
    log(f"{'='*60}")
    log_fh.close()
    sys.exit(0)


# ─── Confirmation prompt before making any changes ───────────────────────────
print(f"\nLog saved to: {LOG_FILE}")
input("\n> Press Enter to start creating branches and PRs on GitHub...")


# ─── STEP 2: Create branch, remove addShortText lines, commit, create PR ──────
log(f"\n{'='*60}")
log("CREATING BRANCHES AND PULL REQUESTS")
log(f"{'='*60}")

for repo_name in sorted_repos:
    log(f"\n{'─'*50}")
    log(f"[REPO] {repo_name}")

    try:
        repo        = org.get_repo(repo_name)
        base_branch = repo.default_branch

        # Check if a PR already exists for this branch
        existing_prs = repo.get_pulls(state="open", head=f"{ORG_NAME}:{BRANCH_NAME}")
        if existing_prs.totalCount > 0:
            log(f"   [SKIPPED] Pull Request already exists: {existing_prs[0].html_url}")
            continue

        # Get the latest commit on the base branch
        base_commit = repo.get_branch(base_branch).commit
        base_sha    = base_commit.sha

        # Create the new branch on GitHub from the base branch SHA
        repo.create_git_ref(ref=f"refs/heads/{BRANCH_NAME}", sha=base_sha)
        log(f"   [OK] Branch created on GitHub: {BRANCH_NAME}")

        # Build a list of new blobs for all changed files
        new_tree_elements = []

        for file_name, line_numbers in repo_hits[repo_name].items():
            try:
                file_obj    = repo.get_contents(file_name, ref=base_branch)
                old_content = file_obj.decoded_content.decode("utf-8", errors="replace")

                new_content = SEARCH_PATTERN.sub(REPLACE_WITH, old_content)

                if new_content == old_content:
                    log(f"   [WARN] No changes produced in '{file_name}' — skipping")
                    continue

                blob = repo.create_git_blob(new_content, "utf-8")
                new_tree_elements.append(
                    InputGitTreeElement(
                        path = file_name,
                        mode = "100644",
                        type = "blob",
                        sha  = blob.sha
                    )
                )
                lines_str = ", ".join(str(n) for n in line_numbers)
                log(f"   [EDITED] {file_name}  (lines removed: {lines_str})")

            except Exception as e:
                log(f"   [ERROR] Cannot edit file '{file_name}': {e}")

        if not new_tree_elements:
            log(f"   [SKIPPED] No files were successfully edited — skipping commit and PR")
            continue

        # Create a new tree on top of the base commit tree
        new_tree = repo.create_git_tree(new_tree_elements, base_commit.commit.tree)

        # Create a single commit containing all changes
        new_commit = repo.create_git_commit(
            message = COMMIT_MESSAGE,
            tree    = new_tree,
            parents = [base_commit.commit]
        )

        # Advance the new branch to the new commit
        repo.get_git_ref(f"heads/{BRANCH_NAME}").edit(sha=new_commit.sha)
        log(f"   [OK] Single commit for all files: '{COMMIT_MESSAGE}'")

        # Create Pull Request
        pr = repo.create_pull(
            title = PR_TITLE,
            body  = PR_BODY,
            head  = BRANCH_NAME,
            base  = base_branch
        )
        log(f"   [PR] {pr.html_url}")

    except Exception as e:
        log(f"   [ERROR] Failed to process repository '{repo_name}': {e}")

log(f"\n{'='*60}")
log("All done!")
log(f"{'='*60}")

log_fh.close()
