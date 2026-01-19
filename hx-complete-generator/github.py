import requests

USER_AGENT = 'hx-complete-generator (https://github.com/pfeif/hx-complete-generator)'


def get_latest_release_version(repo_url: str) -> str:
    """
    Retrieve a project's latest stable release identifier using GitHub's REST API.

    :param str repo_url: the GitHub repository URL
    :returns: the identifier string
    """
    api_url = repo_url.replace('github.com', 'api.github.com/repos') + '/releases/latest'

    headers = {
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': USER_AGENT,
    }

    try:
        response = requests.get(api_url, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()
        version = data.get('tag_name')

        if not version:
            raise SystemExit('No tag_name found in GitHub API response.')

        return version

    except requests.RequestException as error:
        raise SystemExit(error) from error


def download_release_archive(archive_url: str) -> bytes:
    """
    Download a GitHub release archive.

    :param str archive_url: the URL for the release ZIP

    :returns: a binary release file
    """
    headers = {'User-Agent': USER_AGENT}

    try:
        response = requests.get(archive_url, headers=headers, timeout=10)
        response.raise_for_status()

        return response.content
    except requests.RequestException as error:
        raise SystemExit(error) from error
