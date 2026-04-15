"""Diff utilities: parsing and GitHub API fetching."""

import httpx

GITHUB_API_TIMEOUT = 15


def extract_file_patch(full_diff: str, target_path: str) -> str | None:
    """Extract the unified diff patch for a single file from a full diff.

    Returns the patch body or None if the file is not found or is binary.
    """
    marker = f" b/{target_path}"
    sections = full_diff.split("\ndiff --git ")
    for i, section in enumerate(sections):
        if i == 0:
            if section.startswith("diff --git "):
                section = section[len("diff --git "):]
            else:
                continue
        first_newline = section.find("\n")
        if first_newline == -1:
            continue
        header = section[:first_newline]
        if header.endswith(marker):
            body = section[first_newline + 1:]
            if body.startswith("Binary files") and "differ" in body.split("\n")[0]:
                return None
            return body
    return None


async def fetch_github_diff(
    repo: str,
    branch: str,
    base: str,
    token: str,
) -> dict:
    """Fetch full unified diff from GitHub. Tries compare API, falls back to PR.

    Returns {"diff": str} on success or {"error": str, "status": int} on failure.
    """
    headers = {"Authorization": f"token {token}"}

    async with httpx.AsyncClient(timeout=GITHUB_API_TIMEOUT) as http:
        resp = await http.get(
            f"https://api.github.com/repos/{repo}/compare/{base}...{branch}",
            headers={**headers, "Accept": "application/vnd.github.v3.diff"},
        )

        if resp.status_code == 200:
            return {"diff": resp.text}

        if resp.status_code != 404:
            return {"error": f"GitHub API error: {resp.text[:200]}", "status": resp.status_code}

        # Branch deleted — try PR
        pr_resp = await http.get(
            f"https://api.github.com/repos/{repo}/pulls",
            headers={**headers, "Accept": "application/vnd.github+json"},
            params={"head": f"{repo.split('/')[0]}:{branch}", "state": "all", "per_page": 1},
        )

        if pr_resp.status_code != 200 or not pr_resp.json():
            return {"error": "Branch deleted and no PR found — diff unavailable", "status": 404}

        pr_number = pr_resp.json()[0]["number"]
        diff_resp = await http.get(
            f"https://api.github.com/repos/{repo}/pulls/{pr_number}",
            headers={**headers, "Accept": "application/vnd.github.v3.diff"},
        )

        if diff_resp.status_code != 200:
            return {"error": "Could not fetch PR diff", "status": diff_resp.status_code}

        return {"diff": diff_resp.text}
