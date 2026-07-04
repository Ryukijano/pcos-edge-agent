---
name: security-audit
description: Audit PCOS codebase for privacy and security issues
allowed-tools:
  - read
  - grep
  - glob
  - exec
triggers:
  - user
  - model
---

Perform a security audit of the PCOS edge agent codebase:

1. Check all cloud escalation paths in `broker/policies/escalation.py`:
   - Verify PII stripping happens before any cloud call
   - Check that `is_safe_for_cloud()` is called before escalation
   - Verify sensitivity levels are enforced

2. Check `broker/policies/privacy.py`:
   - Verify all PII regex patterns are comprehensive
   - Check that `_REPLACEMENTS` covers all sensitive data types
   - Look for any path that could bypass `strip_pii()`

3. Check API keys and secrets:
   - Search for hardcoded keys: `grep -r "api_key\|token\|secret" --include="*.py" --include="*.kt"`
   - Verify all secrets come from env vars or config files
   - Check `.env.example` has no real secrets

4. Check Android manifest permissions:
   - Read `apps/android/app/src/main/AndroidManifest.xml`
   - Verify no unnecessary permissions
   - Check `uses-native-library` declarations

5. Check Chrome extension:
   - Read `apps/chrome-extension/` files
   - Verify no external data exfiltration
   - Check CSP headers and permissions

6. Report findings categorized by severity (Critical/High/Medium/Low).
