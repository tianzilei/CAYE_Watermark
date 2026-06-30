# WebUI MVP Plan

## Goal

Build the simplest possible local WebUI for `caye-watermark`, with the product focus on:

- user uploads one `DNG`
- user fills EXIF-style fields manually
- watermark footer layout auto-reflows when fields are missing
- user previews the result
- user exports one final `PNG`

The existing CLI remains a debugging and engine layer. The main user-facing workflow should move to WebUI.

## Technology Choice

Use `Gradio Blocks`.

Why this choice:

- simplest path to a working local WebUI
- built-in support for file upload, form inputs, image preview, and download
- no separate frontend stack required
- easy to wire directly into the existing Python pipeline
- good fit for single-page tools with form-driven image generation

Do not use in the MVP:

- FastAPI + custom frontend
- React/Vue frontend
- database
- auth
- batch queue system

## MVP Scope

### In Scope

- local WebUI only
- single-image processing
- one uploaded `DNG`
- one selected logo
- template selection
- manual EXIF-style form fields
- preview action
- export action
- status/progress display

### Out of Scope

- automatic EXIF extraction
- multi-image batch processing
- project/history management
- cloud deployment
- user accounts
- advanced template editor
- drag-and-drop layout designer

## UX Flow

1. User opens the local WebUI.
2. User uploads a `DNG`.
3. User selects a watermark template.
4. User uploads or keeps the default logo.
5. User fills any EXIF-style fields they want.
6. User clicks `Preview`.
7. UI shows the rendered preview and status updates.
8. User adjusts fields if needed.
9. User clicks `Export PNG`.
10. UI returns a downloadable final file.

## Form Fields

These should map directly to `ManualExif` and existing processing options:

- `camera_model`
- `lens_model`
- `focal_length_35mm`
- `aperture`
- `shutter_speed`
- `iso`
- `captured_at`
- `template`
- `watermark_image`
- `upscale_factor`
- `restoration_profile`
- `opacity`

Optional for MVP:

- `no_watermark`
- `watermark_scale`

## UI Layout

Use a single-page two-column layout.

### Left Column

- `DNG` upload
- template dropdown
- logo upload
- EXIF-style text inputs
- processing options
- `Preview` button
- `Export PNG` button

### Right Column

- preview image
- status text / progress log
- downloadable output file

## Architecture

### Recommended Files

- [src/caye_watermark/pipeline.py](/Users/zileitian/Downloads/CAYE_Watermark/src/caye_watermark/pipeline.py)
  Core image restoration and watermark rendering logic.
- [src/caye_watermark/webui.py](/Users/zileitian/Downloads/CAYE_Watermark/src/caye_watermark/webui.py)
  Gradio UI definition and event wiring.
- [src/caye_watermark/cli.py](/Users/zileitian/Downloads/CAYE_Watermark/src/caye_watermark/cli.py)
  Keep as debug/engine entrypoint.

### Data Flow

1. WebUI collects form inputs.
2. Inputs are converted into `ProcessingOptions` and `ManualExif`.
3. WebUI calls the same pipeline functions already used by CLI.
4. Preview output is written to a temporary file.
5. Final export writes a full-resolution PNG and returns it for download.

## Implementation Plan

### Phase 1: Add WebUI Entry

- add `gradio` dependency in [pyproject.toml](/Users/zileitian/Downloads/CAYE_Watermark/pyproject.toml)
- create [src/caye_watermark/webui.py](/Users/zileitian/Downloads/CAYE_Watermark/src/caye_watermark/webui.py)
- add a launchable app function, for example `launch_app()`
- optionally add a console script such as `caye-watermark-web`

Deliverable:

- app launches locally in browser

### Phase 2: Build Basic Form

- add DNG upload
- add template dropdown
- add logo upload
- add EXIF-style text fields
- add preview and export buttons
- add image preview panel

Deliverable:

- static UI renders and accepts inputs

### Phase 3: Wire Preview

- convert uploaded files into local temp paths
- map form values into `ProcessingOptions` and `ManualExif`
- call the pipeline with a preview-oriented path
- return preview image and progress messages

Implementation note:

- keep preview simple first
- if preview feels too slow, add a separate lower-cost preview mode later

Deliverable:

- clicking `Preview` produces a visible image result

### Phase 4: Wire Final Export

- reuse the same input mapping
- run full pipeline
- return downloadable PNG file

Deliverable:

- clicking `Export PNG` returns final output file

### Phase 5: Polish for GUI Use

- make labels user-friendly
- group EXIF-style fields visually
- show helpful empty-state messages
- display processing failures clearly
- confirm missing fields still produce stable layouts

Deliverable:

- MVP is usable without terminal knowledge

## Layout Rules

The WebUI should rely on the backend layout engine already in place.

Rules:

- empty EXIF-style fields should not render placeholder junk
- missing lines should collapse automatically
- GUI should not implement layout branching itself
- all layout decisions stay in the Python rendering layer

## Temporary File Strategy

Use temporary files for MVP.

- uploaded DNG stored in temp location
- preview PNG stored in temp location
- export PNG stored in temp location

Cleanup can be minimal in MVP as long as:

- temp files do not overwrite user files
- export path is stable enough for download

## Error Handling

Show clear UI errors for:

- missing input file
- missing logo when watermark is enabled
- unsupported file type
- pipeline processing failure
- export failure

## Validation Checklist

- preview works with all three footer-style templates
- preview works with all EXIF-style fields empty
- preview works with only one or two fields filled
- export PNG matches selected template
- no terminal is needed for normal use
- CLI still works after WebUI is added

## Suggested Order Of Work

1. Add `gradio`
2. Create `webui.py`
3. Build static form
4. Wire preview
5. Wire export
6. Test missing-field layout cases
7. Update README with launch instructions

## Success Criteria

The MVP is successful if:

- a non-technical user can open the app locally
- they can upload one DNG
- they can fill manual EXIF-style fields
- they can see a preview without using the terminal
- they can export one final PNG

## Nice-To-Have Later

- side-by-side original vs preview
- template thumbnails
- remember last-used settings
- batch export
- packaged desktop build
- richer progress indicator
