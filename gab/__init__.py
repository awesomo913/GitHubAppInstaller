"""GitHub App Manager — backend utilities (zip safety, git auth, credentials)."""

from gab.zip_safe import extract_zip_safely, extract_tar_safely
from gab.git_clone import (
    git_auth_prefix_args,
    git_clone_args,
    git_env_no_prompt,
    git_fetch_origin_depth_args,
    git_merge_ff_fetch_head_args,
    git_pull_args,
    github_auth_header_value,
)
from gab.credentials import TokenStore

__all__ = [
    "extract_zip_safely",
    "extract_tar_safely",
    "git_auth_prefix_args",
    "git_clone_args",
    "git_env_no_prompt",
    "git_fetch_origin_depth_args",
    "git_merge_ff_fetch_head_args",
    "git_pull_args",
    "github_auth_header_value",
    "TokenStore",
]
