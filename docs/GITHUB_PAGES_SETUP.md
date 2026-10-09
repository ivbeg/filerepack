# GitHub Pages deployment setup

This document describes how filerepack documentation is deployed to GitHub Pages at
`https://ivbeg.github.io/filerepack/`.

## Prerequisites

1. The repository `ivbeg/filerepack`
2. GitHub Pages enabled in repository settings with **GitHub Actions** as the source

## Configuration

The documentation is configured in `docs/docusaurus.config.js` for project-site
deployment from this repository:

- **URL**: `https://ivbeg.github.io`
- **Base URL**: `/filerepack/`
- **Organization**: `ivbeg`
- **Project**: `filerepack`

The published site is available at `https://ivbeg.github.io/filerepack/`.

## Setup steps

1. **Enable GitHub Pages**:
   - Go to the repository settings on GitHub
   - Navigate to **Pages** in the left sidebar
   - Under **Source**, select **GitHub Actions** as the source
   - This creates the `github-pages` environment

2. **Push to the default branch**:
   - The GitHub Actions workflow (`.github/workflows/deploy-docs.yml`) will:
     - Build the Docusaurus site when changes are pushed to `master` or `main`
     - Deploy to GitHub Pages
   - The workflow triggers on:
     - Pushes to `master`/`main` that affect files in `docs/`
     - Pushes to `master`/`main` that change `.github/workflows/deploy-docs.yml`
     - Manual workflow dispatch

3. **Verify deployment**:
   - After the workflow completes, the site is available at
     `https://ivbeg.github.io/filerepack/`
   - Check both build and deployment jobs; a successful local build alone does
     not confirm publication

## Moving to a custom domain or user site

If the documentation should later live at a root domain, update
`docusaurus.config.js`:

```javascript
url: 'https://your-domain.example',
baseUrl: '/',
organizationName: 'ivbeg',
projectName: 'filerepack',
```

and configure the domain in the repository's Pages settings.

## Manual workflow deployment

Use the same Actions workflow when deploying an existing branch manually:

1. Open **Actions → Deploy Documentation to GitHub Pages** in the repository.
2. Select **Run workflow**, choose the intended branch and start the run.
3. Check the `github-pages` environment for any required deployment approval.
4. Verify the deployed site after both jobs finish.

The workflow installs locked dependencies with `npm ci`, builds with Node.js 20,
uploads `docs/build` and deploys that artifact using the workflow's Pages and
OIDC permissions. No personal `GITHUB_TOKEN` is needed for this route.

`npm run deploy` invokes Docusaurus's separate Git-branch deployment mechanism
and pushes to `gh-pages`; it is not the artifact deployment used by this
repository's **GitHub Actions** Pages source. See the
[Docusaurus deployment guide](https://docusaurus.io/docs/deployment#deploying-to-github-pages)
before intentionally adopting that alternative.

## Troubleshooting

- **Environment error**: Enable GitHub Pages with **GitHub Actions** as the source
- **Build failures**: Check the GitHub Actions logs; `onBrokenLinks: 'throw'` fails the build on missing routes
- **404 errors**: Verify `baseUrl` in `docusaurus.config.js` is `/filerepack/`
