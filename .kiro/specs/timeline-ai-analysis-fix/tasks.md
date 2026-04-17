# Implementation Plan: Timeline AI Analysis Fix

## Overview

Fix the `aiTimelineAnalysis()` function in `src/frontend/investigator.html` to properly detect and surface HTTP errors from the AI analysis API endpoint. The function currently lacks a `resp.ok` check, causing non-200 responses to silently fail with a misleading "No analysis returned" message.

## Tasks

- [x] 1. Fix aiTimelineAnalysis() error handling in investigator.html
  - [x] 1.1 Add `resp.ok` check after fetch() call in `aiTimelineAnalysis()` function
    - In `src/frontend/investigator.html`, locate the `aiTimelineAnalysis()` function (~line 4432)
    - After `clearTimeout(timeoutId);` and before `let res = await resp.json();`, add a `resp.ok` check
    - If `!resp.ok`, read the response as text, attempt to parse error details from the JSON body (handling both raw error messages and Lambda proxy envelopes with `statusCode`/`body` fields)
    - Throw an Error with the extracted message — this falls into the existing `catch(e)` block which already renders errors with a Retry button
    - Follow the same pattern used in `loadTimeline()` which already handles this correctly
    - _Bugfix Requirements: 2.1, 2.2, 2.3_
    - _Regression Prevention: 3.1, 3.2, 3.3, 3.4, 3.5_
