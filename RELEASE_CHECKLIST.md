# Release Checklist

## Pre-Release
- [ ] Backend stable — all tests pass (882+)
- [ ] Frontend builds without errors (npm run build)
- [ ] Tauri desktop build succeeds (npm run tauri:build)
- [ ] Installer generates successfully (NSIS + MSI)
- [ ] Version numbers consistent (Cargo.toml, __init__.py, tauri.conf.json)
- [ ] CHANGELOG.md updated
- [ ] Documentation complete and accurate
- [ ] Auto-update system tested
- [ ] Sidecar binary built and bundled

## Security
- [ ] No secrets committed
- [ ] .gitignore audit complete
- [ ] Security policies reviewed
- [ ] Dependency vulnerabilities checked

## Documentation
- [ ] README.md up to date
- [ ] INSTALLATION.md accurate
- [ ] BUILD.md matches build process
- [ ] ARCHITECTURE.md reflects current state
- [ ] All API endpoints documented
- [ ] Troubleshooting guide current

## Release
- [ ] Tag version (git tag v1.0.0)
- [ ] Push tag to GitHub
- [ ] GitHub Actions CI/CD runs
- [ ] Release artifacts uploaded
- [ ] Release notes published

## Post-Release
- [ ] Verify installer on clean machine
- [ ] Test update from previous version
- [ ] Monitor issue tracker for feedback
- [ ] Update ROADMAP.md
