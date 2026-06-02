import os
from datetime import datetime
from github import Github, InputGitTreeElement, GithubException

# ─── Configuration ────────────────────────────────────────────────────────────
GITHUB_URL      = "https://github.wdf.sap.corp"
GITHUB_TOKEN    = os.environ.get("GITHUB_TOKEN")
ORG_NAME        = "Portal-CF"
OLD_URL         = "https://i7x.wdf.sap.corp"
NEW_URL         = "https://i7x.bss.net.sap"
BRANCH_NAME     = "BLDXWZ-2501-fix-i7-url"
COMMIT_MESSAGE  = "Update URL for i7"
PR_TITLE        = "[BLDXWZ-2501]-fix-i7-url"
PR_BODY         = "Replaces `https://i7x.wdf.sap.corp` → `https://i7x.bss.net.sap`"
SCAN_EXTENSIONS = {".json", ".yml", ".yaml", ".groovy", ".md"}
LOGS_DIR        = os.path.join(os.getcwd(), "logs")
LOG_FILE        = os.path.join(LOGS_DIR, f"update_i7_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

# If repository list is not empty — scan only these repositories. Otherwise, scan the entire organization.
REPOSITORY_LIST = [
                    # "ci-demo",
                    # "ci-demo",
                    # "ci-demo",
                    ]


# ─── Initialization ───────────────────────────────────────────────────────────
os.makedirs(LOGS_DIR, exist_ok=True)
g = Github(base_url=f"{GITHUB_URL}/api/v3", login_or_token=GITHUB_TOKEN)
log_fh = open(LOG_FILE, "w", encoding="utf-8")

def log(msg):
    print(msg)
    log_fh.write(msg + "\n")
    log_fh.flush()

# ─── STEP 1: Scan repositories for OLD_URL ────────────────────────────────────
log(f"{'='*60}")
log(f"Scanning organization: {ORG_NAME}")
log(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
log(f"{'='*60}\n")

org = g.get_organization(ORG_NAME)

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

# repo_hits = { repo_name: { file_path: [line_numbers] } }
repo_hits = {}

for i, repo in enumerate(all_repos, 1):
    try:
        base_branch = repo.default_branch
        print(f"[{i}/{len(all_repos)}] Scanning: {repo.name} ({base_branch})", end=" ... ", flush=True)

        # Fetch the full file tree in a single API request
        tree = repo.get_git_tree(base_branch, recursive=True).tree
        relevant = [f for f in tree if f.type == "blob"
                    and any(f.path.endswith(ext) for ext in SCAN_EXTENSIONS)]

        file_hits = {}
        for file_item in relevant:
            try:
                content = repo.get_contents(file_item.path, ref=base_branch)
                text = content.decoded_content.decode("utf-8", errors="replace")
                if OLD_URL in text:
                    lines_with_url = [
                        lineno
                        for lineno, line in enumerate(text.splitlines(), 1)
                        if OLD_URL in line
                    ]
                    file_hits[file_item.path] = lines_with_url
            except Exception as e:
                log(f"\n[ERROR] Cannot read file '{file_item.path}' in '{repo.name}': {e}")

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
log(f"SCAN RESULTS — repositories containing {OLD_URL}")
log(f"Repositories found: {len(sorted_repos)}")
log(f"{'='*60}")

for repo_name in sorted_repos:
    log(f"\n[REPO] {repo_name}")
    for file_path, line_numbers in sorted(repo_hits[repo_name].items()):
        lines_str = ", ".join(str(n) for n in line_numbers)
        log(f"   [FILE] {file_path}  (lines: {lines_str})")

log(f"\n{'='*60}\n")
print(f"\nLog saved to: {LOG_FILE}")
input("\n> Press Enter to start creating branches and PRs on GitHub...")

# ─── STEP 2: Create branch, edit files via API, commit, create PR ─────────────
log(f"\n{'='*60}")
log("CREATING BRANCHES AND PULL REQUESTS")
log(f"{'='*60}")

for repo_name in sorted_repos:
    log(f"\n{'─'*50}")
    log(f"[REPO] {repo_name}")

    try:
        repo        = org.get_repo(repo_name)
        base_branch = repo.default_branch

        # Check if PR already exists for this branch
        existing_prs = repo.get_pulls(state="open", head=f"{ORG_NAME}:{BRANCH_NAME}")
        if existing_prs.totalCount > 0:
            log(f"   [SKIPPED] Pull Request already exists: {existing_prs[0].html_url}")
            continue

        # Get the latest commit on base branch
        base_commit = repo.get_branch(base_branch).commit
        base_sha    = base_commit.sha

        # Create new branch on GitHub from base branch SHA
        repo.create_git_ref(ref=f"refs/heads/{BRANCH_NAME}", sha=base_sha)
        log(f"   [OK] Branch created on GitHub: {BRANCH_NAME}")

        # Build a list of new blobs for all changed files
        new_tree_elements = []
        for file_path, line_numbers in repo_hits[repo_name].items():
            try:
                # Read current file content from base branch
                file_obj    = repo.get_contents(file_path, ref=base_branch)
                old_content = file_obj.decoded_content.decode("utf-8", errors="replace")
                new_content = old_content.replace(OLD_URL, NEW_URL)

                # Create a blob with updated content
                blob = repo.create_git_blob(new_content, "utf-8")
                new_tree_elements.append(
                    InputGitTreeElement(
                        path = file_path,
                        mode = "100644",
                        type = "blob",
                        sha  = blob.sha
                    )
                )
                lines_str = ", ".join(str(n) for n in line_numbers)
                log(f"   [EDITED] {file_path}  (lines: {lines_str})")

            except Exception as e:
                log(f"   [ERROR] Cannot edit file '{file_path}': {e}")

        if not new_tree_elements:
            log(f"   [SKIPPED] No files were successfully edited, skipping commit and PR")
            continue

        # Create a new tree on top of the base commit tree
        new_tree = repo.create_git_tree(new_tree_elements, base_commit.commit.tree)

        # Create a single commit with all changes
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

