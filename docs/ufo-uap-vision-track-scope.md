# PURSUE Vision-Analysis Track — Scope

*Frame-level analysis of the PURSUE video/imagery tranches to derive sensor-level signatures the text pipeline cannot. Design/scope only — not yet built.*

## Why a separate track
The text pipeline (Tier-1 → 31 signatures → ingest) is done and validated across NUFORC/UPDB/GEIPAN/PURSUE. It captures the *phenomenology* — including maritime/USO from OCR text. What it CANNOT capture is what only exists in the footage itself:
- **Kinematics measured from pixels** (angular velocity, right-angle turns, hover stability) rather than described in words.
- **Sensor artifacts** (FLIR glare/rotation, parallax, tracking-gate behavior) that separate genuine anomalies from instrument effects.
- **Object morphology from imagery** (sphere/tic-tac/triangle) confirmed visually, not just from a witness phrase.

The recency search confirmed the payoff target: **PR067 (Release 02) — first official USO footage** (spheres in/out of water near a submarine), the Lake Huron F-16 shootdown video, and 19+ AARO "unresolved" infrared clips. These are the ground truth for the maritime + kinematic signatures we authored from text.

## What data is available (from the 2026 re-search)
- **PURSUE Releases 01–05**: ~375 files; the video subset is ~28 (R1) + more per tranche — MP4/infrared clips.
- **AARO imagery catalog**: individual IR video cases (Army 2026, Indo-Pacific, EUCOM 2024).
- **CAVEAT (confirmed):** there is NO public dump of RAW sensor data (radar tracks, FLIR telemetry). Public = the rendered video/imagery + reports. So vision analysis works on the *rendered footage*, not raw sensor streams. This bounds what's derivable (visual kinematics yes; calibrated radar cross-section no).

## Reuse what's already built (do NOT reinvent)
The repo already has a vision pipeline — reference it:
- **`rekognition` pipeline-config section** (`config_validation_service.py`): `video_processing_mode` (skip/faces_only/targeted/full), `video_segment_length_seconds`, object/label detection, `min_object_confidence`.
- **`image_description` section**: Bedrock vision model (`model_id`, `custom_prompt`, `max_images_per_run`) — for narrating frames.
- **Ingestion Rekognition Lambdas** (`ResearchAnalystStack-IngestionRekognitionLambda*`, `FaceCropLambda`) already in the Step Function.
- **`cost_estimation_service.py`** already prices Rekognition image + video by mode.

## Proposed approach (tiered, mirrors the text loop)
1. **Acquire** video/imagery from the community mirrors (warufo.com / socialmediaforaliens.com) or war.gov directly; store in `docs/pursue/video/`. (Git-LFS or direct download.)
2. **Tier-1 (cheap frame sampling):** ffmpeg-extract keyframes (1 fps) → Rekognition label/object detection (`video_processing_mode: targeted`) to find frames containing an object of interest. Discards empty/sky frames. ~$0.10/min of video.
3. **Tier-2 (vision narration):** send only object-bearing keyframes to the Bedrock vision model (`image_description`) with a UAP-specific prompt ("describe object shape, motion across frames, sensor artifacts, water interaction"). Produces text descriptions.
4. **Tier-3 (feed the EXISTING pipeline):** the frame descriptions become documents → run through the SAME text signature scan (31 signatures) + ingest via the built pipeline. This unifies vision output with the text corpus — no separate scoring path.
5. **New signature candidates** to look for in the footage (author only if the data supports, per master-loop): `uap-vis-flir-rotation` (FLIR glare rotating with gimbal ≠ object rotation), `uap-vis-kinematic-measured` (pixel-tracked angular rate), `uap-vis-uso-transition` (visual air↔water crossing — validate against PR067).

## Cost / effort estimate
- Acquisition: manual/LFS, ~2.4 GB per tranche of video.
- Frame extraction + Rekognition: ~$0.10–0.20 per video-minute (targeted mode); the PURSUE video set is tens of minutes total → **~$5–15**.
- Bedrock vision narration on keyframes: ~$0.001–0.003/frame → **~$5–20** depending on frame count.
- Total first pass: **~$15–40**, one-time. Uses existing infra (no new services).

## Deliverables
- `scripts/_extract_pursue_frames.py` (ffmpeg keyframe sampling)
- Reuse Rekognition + image_description pipeline sections (config, not new code)
- Frame-description documents ingested into the `ufos_uaps` case set
- Vision gap-analysis run through `taxonomy_enrichment_loop.py` → AUGMENT/STOP verdict on vision-derived signatures
- Validation target: does the footage confirm `uap-fk-tm-001/002/003` (maritime) and the kinematic signatures?

## Recommendation
Medium effort, ~$15–40, high demonstrative value (official USO footage validating our text-derived maritime signatures). But it's a distinct build with a vision dependency (ffmpeg + Rekognition + Bedrock vision). Suggest doing it as its own focused session after loading PURSUE text Releases 02–05 (which is the cheaper, higher-coverage next step and needs no vision stack).
