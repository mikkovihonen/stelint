"""Create a GitHub release, skipping if it already exists."""

import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds


def github_api_request(
    url: str,
    headers: dict,
    method: str = "GET",
    data: bytes | None = None,
) -> tuple[int, str]:
    """Make an HTTP request to the GitHub API with retry logic."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            request = Request(url, data=data, headers=headers, method=method)
            with urlopen(request, timeout=30) as response:
                body = response.read().decode("utf-8")
                return response.status, body
        except HTTPError as exc:
            body = exc.read().decode("utf-8")
            if exc.code == 422:
                # 422 means resource already exists — not retryable
                return exc.code, body
            if exc.code in (429, 500, 502, 503, 504):
                if attempt < MAX_RETRIES:
                    backoff = INITIAL_BACKOFF * (2 ** (attempt - 1))
                    print(
                        f"Retryable error ({exc.code}). Retrying in {backoff:.1f}s (attempt {attempt}/{MAX_RETRIES})...",
                        file=sys.stderr,
                    )
                    time.sleep(backoff)
                    continue
                raise SystemExit(f"GitHub API error {exc.code} after {MAX_RETRIES} retries: {body}")
            raise SystemExit(f"GitHub API error {exc.code}: {body}")
        except URLError as exc:
            if attempt < MAX_RETRIES:
                backoff = INITIAL_BACKOFF * (2 ** (attempt - 1))
                print(
                    f"Network error: {exc.reason}. Retrying in {backoff:.1f}s (attempt {attempt}/{MAX_RETRIES})...",
                    file=sys.stderr,
                )
                time.sleep(backoff)
                continue
            raise SystemExit(f"Network error after {MAX_RETRIES} retries: {exc.reason}")

    # Should not reach here, but just in case
    raise SystemExit("Unexpected state in retry loop.")


def release_exists(repo: str, tag: str, token: str) -> bool:
    """Check whether a release with the given tag already exists."""
    url = f"https://api.github.com/repos/{repo}/releases/tags/{tag}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "stelint-publish-script",
    }
    status, _ = github_api_request(url, headers, method="GET")
    return status == 200


def main() -> None:
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    tag = os.environ.get("RELEASE_TAG")
    name = os.environ.get("RELEASE_NAME")
    body = os.environ.get("RELEASE_NOTES", "")

    if not token:
        raise SystemExit("Missing GITHUB_TOKEN environment variable")
    if not repo:
        raise SystemExit("Missing GITHUB_REPOSITORY environment variable")
    if not tag or not name:
        raise SystemExit("Missing RELEASE_TAG or RELEASE_NAME environment variable")

    # Idempotency: skip if release already exists
    if release_exists(repo, tag, token):
        print(f"Release for tag {tag!r} already exists. Skipping creation.")
        return

    payload = json.dumps(
        {
            "tag_name": tag,
            "name": name,
            "body": body,
            "draft": False,
            "prerelease": False,
        },
        ensure_ascii=False,
    ).encode("utf-8")

    url = f"https://api.github.com/repos/{repo}/releases"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "stelint-publish-script",
    }

    status, resp_body = github_api_request(url, headers, method="POST", data=payload)

    if status == 201:
        data = json.loads(resp_body)
        print("Release created:", data.get("html_url"))
    elif status == 422:
        raise SystemExit(f"Release creation failed (422). The tag {tag!r} may already be in use by a non-release git reference. Response: {resp_body}")
    else:
        raise SystemExit(f"GitHub API error {status}: {resp_body}")


if __name__ == "__main__":
    main()
