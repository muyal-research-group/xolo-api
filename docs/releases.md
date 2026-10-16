# Releases

The repository uses independent tags so the API and Python client can evolve without forcing an unrelated release.

```text
push / pull request
        |
        +--> API tests (MongoDB + Redis)
        +--> client contract tests + package build
        +--> Nuxt UI production build
        +--> API docs + client docs build

push to main/master
        |
        +--> build both Zensical sites --> deploy GitHub Pages

api-vX.Y.Z tag       --> verify API version --> test --> publish Docker Hub API image
client-vX.Y.Z tag    --> verify client version --> test/build --> publish to PyPI
ui-vX.Y.Z tag        --> verify UI version --> build --> publish Docker Hub UI image
```

## API image

1. Set the version in the root `pyproject.toml`.
2. Commit and push the change.
3. Create and push a matching tag, for example `api-v0.1.0a5`.

The workflow publishes a multi-architecture image to:

- `nachocode/xolo:api-0.1.0a5`

A stable semantic version such as `api-v0.1.0` also updates `nachocode/xolo:api-latest`. Pre-releases never update that moving tag. GitHub Actions authenticates with the `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` repository secrets.

## Python client

1. Set the version in `xolo-client/pyproject.toml`.
2. Commit and push the change.
3. Create and push a matching tag, for example `client-v0.1.0a5`.

The workflow tests and builds the wheel and source distribution, then publishes package `xolo` to TestPyPI through Trusted Publishing. Configure a TestPyPI trusted publisher for this repository, workflow `release-client.yml`, and environment `testpypi`. The publisher's repository owner and name must match the repository where the tag is pushed. No long-lived API token is stored in GitHub.

## UI image

1. Set `xolo-ui/VERSION` to the same version used by the component release.
2. Commit and push the change.
3. Create and push the matching tag, for example `ui-v0.1.0a5`.

The workflow builds the Nuxt application and publishes `nachocode/xolo:ui-0.1.0a5`. A stable version also updates `nachocode/xolo:ui-latest`.

The tags are intentionally component-specific. An API-only change publishes only `api-v*`; a UI-only change publishes only `ui-v*`; and a client-only change publishes only `client-v*`. Use the same version value across all components when releasing a coordinated set.

For a coordinated release of all three components, set the same version in the root and client `pyproject.toml` files and `xolo-ui/VERSION`, then commit those changes. Run `./scripts/create-release-tags 0.1.0a8` to create all three annotated tags locally, or add `--push` to push them to `origin` and trigger the release workflows. The script refuses mismatched versions, uncommitted changes, and existing tags. It does not change version files or push your branch.

## Documentation

GitHub Pages deploys the API documentation at the site root and the client documentation below `/client/`. In the repository settings, select **GitHub Actions** as the Pages source. The workflow uses only GitHub's short-lived Pages token.
