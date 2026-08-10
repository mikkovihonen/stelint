#!/usr/bin/env python3
import json
import os
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def main() -> None:
    token = os.environ.get('GITHUB_TOKEN')
    repo = os.environ.get('GITHUB_REPOSITORY')
    tag = os.environ.get('RELEASE_TAG')
    name = os.environ.get('RELEASE_NAME')
    body = os.environ.get('RELEASE_NOTES', '')

    if not token:
        raise SystemExit('Missing GITHUB_TOKEN environment variable')
    if not repo:
        raise SystemExit('Missing GITHUB_REPOSITORY environment variable')
    if not tag or not name:
        raise SystemExit('Missing RELEASE_TAG or RELEASE_NAME environment variable')

    payload = json.dumps(
        {
            'tag_name': tag,
            'name': name,
            'body': body,
            'draft': False,
            'prerelease': False,
        },
        ensure_ascii=False,
    ).encode('utf-8')

    url = f'https://api.github.com/repos/{repo}/releases'
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
        'Content-Type': 'application/json',
        'User-Agent': 'stelint-publish-script',
    }

    request = Request(url, data=payload, headers=headers, method='POST')

    try:
        with urlopen(request) as response:
            data = json.loads(response.read().decode('utf-8'))
            print('Release created:', data.get('html_url'))
    except HTTPError as exc:
        message = exc.read().decode('utf-8')
        raise SystemExit(f'GitHub API error {exc.code}: {message}')


if __name__ == '__main__':
    main()
