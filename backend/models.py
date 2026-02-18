"""
Pydantic models for app creation API.
"""
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    PUSHING = "pushing"
    DEPLOYING = "deploying"
    DONE = "done"
    FAILED = "failed"


# ----- Request: POST /api/apps/create -----


class GitConnection(BaseModel):
    provider: str = "github"
    token: str = Field(..., min_length=1, description="Git personal access token")
    repo_url: Optional[str] = Field(None, description="Existing repo URL (https). If omitted, create new repo.")
    create_new: bool = Field(False, description="If true and repo_url empty, create a new repository")


class VercelConnection(BaseModel):
    token: str = Field(..., min_length=1, description="Vercel API token")
    team_id: Optional[str] = None
    project_name: Optional[str] = None


class CreateAppRequest(BaseModel):
    app_name: str = Field(..., min_length=1, max_length=100)
    description: str = Field("", max_length=2000)
    prompt: str = Field(..., min_length=1, max_length=10000)
    git: GitConnection
    vercel: VercelConnection


# ----- Response: POST /api/apps/create -----


class CreateAppResponse(BaseModel):
    job_id: str
    message: str = "App creation started. Poll GET /api/apps/status/{job_id} for progress."


# ----- Response: GET /api/apps/status/{job_id} -----


class AppStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: Optional[str] = None
    repo_url: Optional[str] = None
    deploy_url: Optional[str] = None
    error: Optional[str] = None
    details: Optional[dict[str, Any]] = None


# ----- Agent API models -----


class CreateSessionRequest(BaseModel):
    initial_message: Optional[str] = Field(None, max_length=10000)


class CreateSessionResponse(BaseModel):
    session_id: str
    reply: Optional[str] = None
    message_history: Optional[list[dict]] = None


class SendMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)


class SendMessageResponse(BaseModel):
    reply: str
    tool_summary: Optional[list[str]] = None


class AgentDeployRequest(BaseModel):
    app_name: str = Field(..., min_length=1, max_length=100)
    git: GitConnection
    vercel: VercelConnection


class AgentDeployResponse(BaseModel):
    repo_url: str
    deploy_url: Optional[str] = None
    error: Optional[str] = None


class FileEntry(BaseModel):
    name: str
    type: str  # "file" | "directory"
    path: Optional[str] = None


class FilesResponse(BaseModel):
    entries: list[FileEntry]
    path: str
