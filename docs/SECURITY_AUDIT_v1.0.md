# PCOS v1.0.0 Security Audit

**Audit date:** 2026-07-12  
**Scope:** broker policies, cloud escalation, configuration, Android manifest, Chrome extension, Docker/Hugging Face deployment files, and release dependencies.

## Method

- Reviewed cloud escalation and privacy code paths.
- Reviewed all runtime secret references and `.env.example`.
- Reviewed Android native-library declarations and permissions.
- Reviewed Chrome extension permissions, host permissions, and DOM output handling.
- Reviewed Docker health checks and HF Space container configuration.
- Added automated regression coverage in `tests/test_release_security.py`.
- Ran the complete Python test suite and release smoke checks.

## Findings and remediation

| Severity | Finding | Status |
|---|---|---|
| High | Wildcard CORS was present in broker and compose defaults | Fixed: local-origin defaults; production must set explicit origins |
| High | WebSocket bridge authentication was optional | Fixed: `PCOS_BRIDGE_AUTH_REQUIRED=true` requires a non-empty token |
| Medium | Chrome extension had broad `<all_urls>` host access | Fixed: host permissions limited to local broker; `activeTab` remains for user-invoked page access |
| Medium | Release versions were inconsistent (`0.3.0`, `0.2.0`) | Fixed: package, API, health endpoint, and extension aligned to `1.0.0` |
| Low | No committed release security evidence existed | Fixed: this report and automated regression tests added |

## Positive controls verified

- `models/cloud/escalation_provider.py` calls `strip_pii()` and then `is_safe_for_cloud()` before provider calls.
- Cloud API keys are read from environment variables and are not committed in `.env.example`.
- Android QAIRT and OpenCL native libraries are declared optional.
- Chrome output rendering uses `textContent` in the main sidepanel execution paths.
- Docker and Compose expose health checks for the broker.
- HF Space secrets are expected to be supplied through deployment environment settings, not source files.

## Release gates

- [x] No Critical findings identified in the reviewed scope.
- [x] No unresolved High findings in the reviewed scope.
- [x] Security regression tests pass.
- [x] Full Python test suite passes.
- [ ] Android/iOS Xcode device builds verified on release hardware.
- [ ] Live HF Space deployment smoke-tested after deployment.
- [ ] Dependency vulnerability scan/SBOM generated in CI or release environment.

## Residual risks

- `PCOS_BRIDGE_AUTH_REQUIRED` must be enabled and `PCOS_BRIDGE_AUTH_TOKEN` provisioned for any public broker deployment.
- `PCOS_CORS_ORIGINS` must be explicitly set to the deployed UI origins; never use `[*]` in production.
- The optional LiteRT-LM CLI is not installed in this environment, so device performance numbers cannot be measured here.
- Dependency versions use lower bounds; a release pipeline should run SCA/SBOM tooling against the resolved environment.
