---
description: Deploy PCOS broker to HuggingFace Spaces
---

1. Verify all tests pass:
   ```bash
   python -m pytest tests/ -v --tb=short
   ```

2. Check the Dockerfile is up to date:
   - Read `hf_space/Dockerfile`
   - Verify Python version, dependencies, and entrypoint

3. Check `hf_space/app.py` for any syntax errors:
   ```bash
   python -c "import ast; ast.parse(open('hf_space/app.py').read())"
   ```

4. Verify `hf_space/requirements.txt` has all needed dependencies.

5. Commit all changes:
   ```bash
   git add -A && git commit -m "deploy: update HF Space"
   ```

6. Push to GitHub:
   ```bash
   git push origin main
   ```

7. Report the HuggingFace Space URL: https://huggingface.co/spaces/Ryukijano/pcos-edge-agent
