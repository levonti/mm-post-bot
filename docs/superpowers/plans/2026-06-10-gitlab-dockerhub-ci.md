# GitLab Docker Hub CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add GitLab CI versioning and Docker Hub publishing that builds images only when runtime image inputs changed.

**Architecture:** GitLab CI runs Python validation for merge requests, `main`, and tags. Docker image jobs are guarded by `rules:changes` for branch and MR pipelines, while tag pipelines call a repository-local shell script that compares runtime image inputs to the previous semver tag before any Docker build or push.

**Tech Stack:** GitLab CI, Docker BuildKit, Docker Hub, POSIX shell, Python pytest.

---

### Task 1: Runtime Image Change Decision

**Files:**
- Create: `ci/docker/runtime-image-changed.sh`
- Create: `tests/test_runtime_image_changed_script.py`

- [ ] **Step 1: Write tests**

Create pytest coverage for the shell script. The tests initialize temporary git repositories, add semver tags, and assert that the script exits with:

- `0` when runtime inputs changed after the previous semver tag.
- `1` when only non-runtime files changed.
- `0` when no previous semver tag exists, so the first release is publishable.

- [ ] **Step 2: Run tests to verify red**

Run: `uv run pytest tests/test_runtime_image_changed_script.py`

Expected: fail because `ci/docker/runtime-image-changed.sh` does not exist yet.

- [ ] **Step 3: Implement script**

Create `ci/docker/runtime-image-changed.sh` with a fixed runtime input list:

- `Dockerfile`
- `.dockerignore`
- `pyproject.toml`
- `uv.lock`
- `src/`

The script finds the previous `vX.Y.Z` tag before `HEAD`, diffs only runtime inputs, prints a reason, exits `0` when publish/build should proceed, and exits `1` when it should be skipped.

- [ ] **Step 4: Run tests to verify green**

Run: `uv run pytest tests/test_runtime_image_changed_script.py`

Expected: pass.

### Task 2: Docker Build Context

**Files:**
- Create: `.dockerignore`

- [ ] **Step 1: Add Docker ignore file**

Exclude git metadata, local virtualenv/cache directories, tests, docs, local env files, and worktrees from the Docker build context. Keep `src`, `pyproject.toml`, `uv.lock`, and `Dockerfile` included.

### Task 3: GitLab CI Pipeline

**Files:**
- Create: `.gitlab-ci.yml`

- [ ] **Step 1: Add validation jobs**

Run `uv sync --frozen`, `ruff check`, `mypy`, and `pytest` for merge requests, `main`, and tags.

- [ ] **Step 2: Add MR build-check job**

Build the Docker image without push for merge requests only when runtime image inputs changed.

- [ ] **Step 3: Add `main` publish job**

On `main`, publish `main` and `sha-$CI_COMMIT_SHORT_SHA` tags to Docker Hub only when runtime image inputs changed.

- [ ] **Step 4: Add release publish job**

On semver tags `vX.Y.Z`, verify `pyproject.toml` version equals `X.Y.Z`, reuse the existing `sha-$CI_COMMIT_SHORT_SHA` Docker Hub image if present, or call `ci/docker/runtime-image-changed.sh` before building. Publish `vX.Y.Z`, `X.Y.Z`, and `latest` only when the guard allows publishing.

### Task 4: Verification

**Files:**
- Read: `.gitlab-ci.yml`
- Read: `ci/docker/runtime-image-changed.sh`
- Read: `.dockerignore`

- [ ] **Step 1: Run targeted tests**

Run: `uv run pytest tests/test_runtime_image_changed_script.py`

Expected: pass.

- [ ] **Step 2: Run existing lightweight tests**

Run: `uv run pytest tests/test_main.py`

Expected: pass.

- [ ] **Step 3: Review diff**

Run: `git diff -- .gitlab-ci.yml .dockerignore ci/docker/runtime-image-changed.sh tests/test_runtime_image_changed_script.py docs/superpowers/plans/2026-06-10-gitlab-dockerhub-ci.md`

Expected: changes match the CI design and do not include unrelated edits.
