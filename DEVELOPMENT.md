# Development Workflow

**Miget Container OS** - https://miget.com

## Prerequisites

- Python 3.12+
- Docker with Buildx enabled
- Access to Miget Docker Hub credentials (for publishing)

## Local Development Workflow

### Complete Build and Verification

The recommended workflow to ensure everything is up-to-date before pushing:

```bash
make build-and-verify
```

This single command will:
1. Build all image variants (14 total: Ubuntu 22.04/24.04/26.04 + Alpine 3.21/3.22/3.23/3.24, each with dockerd/podman)
2. Start each container and verify installed package versions
3. Update `manifests/package_versions.json` with actual verified versions
4. Regenerate the README component versions table
5. Clean up test images

### Refreshing Versions and Dockerfiles

1. Update manifest metadata from upstream sources
   ```bash
   python scripts/update_manifest_versions.py
   ```
2. Regenerate Dockerfiles from templates
   ```bash
   python scripts/render_dockerfiles.py
   ```
3. Update README component versions table
   ```bash
   python scripts/update_readme_table.py
   ```
4. Review changes under `dockerfiles/` and manifests

### Quick Commands

```bash
make update-versions  # Fetch latest versions and regenerate everything
make render          # Just regenerate Dockerfiles
make update-readme   # Just update README table
make clean          # Remove test images
```

### Adding New OS Versions (Manual Process)

When a new Ubuntu or Alpine version is released (e.g., Ubuntu 26.04, Alpine 3.23):

1. **Update targets.json**
   ```bash
   # Edit manifests/targets.json
   # Add new OS version entry with package lists
   ```

2. **Create/update templates if needed**
   ```bash
   # Check if templates/ubuntu.Dockerfile.tmpl needs updates
   # Check if templates/alpine.Dockerfile.tmpl needs updates
   ```

3. **Build and verify locally**
   ```bash
   make build-and-verify
   ```

4. **Bump minor version**
   ```bash
   python scripts/bump_version.py --minor
   # This bumps 1.0.0 → 1.1.0
   ```

5. **Commit and push**
   ```bash
   git add -A
   git commit -m "feat: add Ubuntu 26.04 support"
   git push
   ```

**Note**: The automated workflow only tracks package updates within existing OS versions. New OS versions must be added manually.

## Validation

- CI runs `.github/workflows/validate.yml` which:
  - Ensures templates produce reproducible Dockerfiles
  - Prints the build matrix produced by `scripts/build_matrix.py`
  - Performs an alias retag dry-run

For local checks:
```bash
python scripts/render_dockerfiles.py --dry-run
python scripts/build_matrix.py
python scripts/tag_aliases.py --dry-run
```

## Automated Release Workflow

### Daily Checks (Scheduled)

The `.github/workflows/regenerate-dockerfiles.yml` workflow runs daily at 5:00 AM UTC:

1. **Fetch Latest Versions**
   - Queries Docker Hub for latest Docker Compose version
   - Queries package repositories for latest Docker CE, Podman, and OS packages
   - Records Ubuntu base image digests

2. **Detect Significant Changes**
   - Checks if Docker Compose, Docker CE, Podman, or base OS versions changed
   - Only proceeds if significant changes are detected

3. **Create Release PR**
   - Bumps patch version automatically (e.g., 1.0.0 → 1.0.1)
   - Regenerates all Dockerfiles from templates
   - Updates README component versions table
   - Updates CHANGELOG.md
   - Creates a PR titled "Release vX.Y.Z" with `release` and `automated` labels

### On PR Merge to Main

When a release PR is merged to `main`, `.github/workflows/build-and-publish.yml`:

1. **Build Multi-arch Images**
   - Builds all image variants for `linux/amd64` and `linux/arm64`
   - Pushes to Docker Hub `miget/container-os` with version tags

2. **Create GitHub Release**
   - Creates a GitHub release with tag `vX.Y.Z`
   - Includes changelog excerpt in release notes
   - Links to Docker Hub images

3. **Update Aliases**
   - `.github/workflows/update-aliases.yml` retags channel aliases (e.g., `stable-ubuntu22-dockerd`)

### Manual Releases

You can manually trigger a release:

```bash
# Trigger the workflow manually via GitHub UI or:
gh workflow run regenerate-dockerfiles.yml
```

Or locally before pushing:

```bash
make build-and-verify  # Build, verify, and update manifests
git add -A
git commit -m "chore: release vX.Y.Z"
git push
```

## Changelog

- `scripts/update_changelog.py --auto` updates `CHANGELOG.md` using manifest and package information; invoked automatically in scheduled refresh workflow.

## File Overview

### Manifests
- `manifests/targets.json` – OS releases, alias patches, package buckets
- `manifests/package_versions.json` – Verified package versions from built images

### Templates
- `templates/*.Dockerfile.tmpl` – Base templates for Ubuntu/Alpine

### Scripts
- `scripts/build_and_verify.py` – Build all images, verify packages, update manifests
- `scripts/render_dockerfiles.py` – Template renderer
- `scripts/update_manifest_versions.py` – Queries Docker Hub & package managers for updates
- `scripts/update_readme_table.py` – Auto-generates README component versions table
- `scripts/build_matrix.py` – Matrix generation for GitHub Actions
- `scripts/tag_aliases.py` – Retags channel aliases on Docker Hub
- `scripts/update_changelog.py` – Updates CHANGELOG.md

### Build Helpers
- `Makefile` – Convenient commands for local development
