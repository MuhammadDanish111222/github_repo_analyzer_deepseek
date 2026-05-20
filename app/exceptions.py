class RepoAnalyzerError(Exception):
    """Base application error with a safe public message."""

    def __init__(self, public_message: str, status_code: int = 400) -> None:
        super().__init__(public_message)
        self.public_message = public_message
        self.status_code = status_code


class InvalidRepositoryUrlError(RepoAnalyzerError):
    def __init__(self) -> None:
        super().__init__(
            "Invalid GitHub repository URL. Use a public URL like https://github.com/owner/repo.",
            status_code=422,
        )


class GitHubFetchError(RepoAnalyzerError):
    pass


class SourceFileNotFoundError(RepoAnalyzerError):
    def __init__(self) -> None:
        super().__init__(
            "No suitable primary source code file was found in this repository.",
            status_code=404,
        )


class LLMAnalysisError(RepoAnalyzerError):
    def __init__(self, message: str = "The LLM analysis service failed. Please try again later.") -> None:
        super().__init__(message, status_code=502)
