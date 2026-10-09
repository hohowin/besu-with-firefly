---
name: motion
description: Route every motion-graphic, animation, animated diagram, explainer video or "motion picture" request to the HyperFrames and Remotion skills. Trigger whenever the user asks to create, make, render or edit a motion graphic, an animation, an animated GIF/SVG/MP4, a video clip, an intro, a product or PR video, or anything that moves, even if they don't name a tool.
---

# Skill: motion — Motion Graphics Router

## Purpose
Make every motion graphic, animation or video with the **HyperFrames** and **Remotion** skills instead of hand-rolled CSS/SVG animation.

## When to Trigger
- "create a motion graphic / animation / motion picture / video / animated intro"
- "animate this diagram", "make a 10 sec clip", "turn this PR / README / site into a video"
- Any request whose deliverable moves over time

## What to Do

### 1. Make sure both skills are installed
Check for `.agents/skills/hyperframes/SKILL.md` and `.agents/skills/remotion-best-practices/SKILL.md` (or the same under `.claude/skills/`). Install whatever is missing, locally (never `-g`):

```bash
npx skills add heygen-com/hyperframes@hyperframes
npx skills add remotion-dev/skills@remotion-best-practices
```

If an install fails, show the error and stop; don't fall back to hand-written animation without telling the user.

### 2. Load both skills
Invoke `hyperframes` and `remotion-best-practices` with the Skill tool (or read their `SKILL.md` if the session started before they were installed) and follow their instructions for the build.

### 3. Pick the engine, say which and why in one line
| Situation | Engine |
|---|---|
| Quick motion graphic, explainer, title card, HTML/CSS-friendly scene, no React in the project | **HyperFrames** (default) |
| Project already uses React/TypeScript, data-driven or programmatic video, many reusable scenes, captions | **Remotion** |
| Existing Remotion project to port to HTML | HyperFrames (`heygen-com/hyperframes@remotion-to-hyperframes`, install on demand) |

The more specialised HyperFrames skills (`motion-graphics`, `hyperframes-animation`, `hyperframes-cli`, `pr-to-video`, `website-to-hyperframes`, …) and Remotion skills (`remotion-render`, `remotion-captions`, …) are installed on demand with `npx skills add <owner/repo@skill>` when the task needs them.

### 4. Keep the project clean
- Put the motion project (sources, `node_modules`, renders) in its own folder, `videos/<name>/` (the HyperFrames workflows' convention; for Remotion use the same folder), with its own `package.json`; don't add dependencies to the repo root. Gitignore `node_modules/`, `renders/` and `snapshots/` under `videos/`.
- Commit only the source (`videos/<name>/index.html`, `package.json`, …) and the final asset in `docs/images/`.
- The HyperFrames CLI installs skills **globally** (`~/.claude/skills`) when run (`hyperframes skills update`, `hyperframes init`). After running it, copy any new skills into this repo's `.agents/skills/` and `.claude/skills/` and remove the global copies.
- Needs `ffmpeg` and `ffprobe` on PATH (`winget install --id Gyan.FFmpeg -e` on Windows); `npx hyperframes doctor` checks.

### 5. Deliver in a format that works where it will be shown
- **GitHub README:** GitHub plays a GIF or an animated SVG inline from the repo; an MP4 only plays inline when uploaded through the GitHub web UI. Render to MP4, then convert to GIF (e.g. `ffmpeg` with a palette) unless the user wants otherwise. Keep a GIF under ~5 MB.
- **Elsewhere:** MP4 (H.264) by default.
- Give the asset meaningful alt text where it is embedded.

### 6. Verify before reporting done
Render, then look at several frames (start, each scene, end) to check layout, text overflow and timing. Report the duration, resolution, file size and where it is embedded.
