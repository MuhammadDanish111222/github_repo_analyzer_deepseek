from pydantic import BaseModel, ConfigDict, Field, field_validator


class AnalyzeRepoRequest(BaseModel):
    repo_url: str = Field(
        ...,
        min_length=18,
        max_length=300,
        examples=["https://github.com/username/repository"],
    )

    @field_validator("repo_url")
    @classmethod
    def validate_repo_url_format(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("repo_url cannot be empty")
        return stripped


class AnalyzeRepoResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "status": "success",
            "repo_name": "repository-name",
            "vulnerabilities_found": [
                "Unsanitized user input is passed into a shell command, creating command injection risk."
            ],
            "suggestions": "Validate inputs, avoid shell=True, and add automated security tests.",
        }
    })

    status: str = "success"
    repo_name: str
    vulnerabilities_found: list[str]
    suggestions: str


class ErrorResponse(BaseModel):
    status: str = "error"
    detail: str


class SelectedSourceFile(BaseModel):
    repo_name: str
    owner: str
    repo: str
    default_branch: str
    path: str
    size: int
    code: str
