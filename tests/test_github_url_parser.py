import pytest

from app.exceptions import InvalidRepositoryUrlError
from app.services.github_service import parse_github_repo_url


def test_parse_standard_github_url():
    parsed = parse_github_repo_url("https://github.com/owner/repo")

    assert parsed.owner == "owner"
    assert parsed.repo == "repo"
    assert parsed.full_name == "owner/repo"


def test_parse_github_url_with_git_suffix_and_extra_path():
    parsed = parse_github_repo_url("https://github.com/owner/repo.git/issues/1")

    assert parsed.owner == "owner"
    assert parsed.repo == "repo"


@pytest.mark.parametrize(
    "bad_url",
    [
        "",
        "not-a-url",
        "https://gitlab.com/owner/repo",
        "https://github.com/owner",
        "ftp://github.com/owner/repo",
    ],
)
def test_reject_invalid_urls(bad_url):
    with pytest.raises(InvalidRepositoryUrlError):
        parse_github_repo_url(bad_url)
