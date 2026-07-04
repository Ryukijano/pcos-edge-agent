# LiteRT-LM Agent Skills

This directory contains specialized agent skills that guide AI developers to successfully orchestrate, implement, and verify complex development tasks in the LiteRT-LM ecosystem.

## Available Skills

- `create-litert-lm-android-demo-app`: Guides the agent to implement, build, and package a standalone LiteRT-LM Android demo application with backend selection and multi-modality support using Bazel 9.

## Usage

To register and automatically load any of these skills in your agent sessions:

1. Locate your agent's skills directory (the folder where your agent loads custom instructions or skills).
2. Copy the desired skill folder (e.g., `create-litert-lm-android-demo-app`) from this directory into that skills directory:

```bash
# Replace the destination path with your active agent skills directory
cp -r agents/skills/create-litert-lm-android-demo-app /path/to/your/agent/skills/
```

Once copied, the agent will automatically detect and load the skill when resolving related user requests.

### Example Prompt (LiteRT-LM Android Demo App)

To execute the specific LiteRT-LM Android demo application creation skill, use this trigger prompt format:

```
Please create a LiteRT-LM Android demo app

root: ~/litert_lm_litert_lm_maven_integration
Maven Integration scenario
Target: pixel 10
model: gemma 4
```
