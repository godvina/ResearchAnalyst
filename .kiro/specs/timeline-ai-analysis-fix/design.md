# Bugfix Design Document: Timeline AI Analysis Fix

## Overview

The `aiTimelineAnalysis()` function in `src/frontend/investigator.html` silently fails when the backend returns a non-200 HTTP status. The function does not check `resp.ok` before parsing the response as JSON, causing error responses to be treated as empty analysis results. This is a frontend-only fix.

## Root Cause

The `aiTimelineAnalysis()` function (line ~4432 in investigator.html) performs a `fetch()` call to `POST /case-files/{id}/timeline/ai-analysis` but does NOT check `resp.ok` before calling `resp.json()`. When the backend returns a 500 error (e.g., Bedrock timeout), the function:

1. Parses the error response body as JSON
2. Unwraps the Lambda proxy envelope (if present)
3. Accesses `res.analysis` which is `undefined` on error payloads
4. Falls through to the "No analysis returned" message — misleading the user

The existing `loadTimeline()` function in the same file already handles this correctly with a `resp.ok` check pattern.

## Fix Design

### Change 1: Add `resp.ok` check to `aiTimelineAnalysis()`

Add an HTTP status check after the `fetch()` call, before parsing the response body. Follow the same pattern used in `loadTimeline()`:

```javascript
// BEFORE (buggy):
const resp = await fetch(API_URL + '/case-files/'+selectedCaseId+'/timeline/ai-analysis', { ... });
clearTimeout(timeoutId);
let res = await resp.json();

// AFTER (fixed):
const resp = await fetch(API_URL + '/case-files/'+selectedCaseId+'/timeline/ai-analysis', { ... });
clearTimeout(timeoutId);
if (!resp.ok) {
    const errText = await resp.text();
    let errMsg = 'API returned ' + resp.status;
    try {
        const errJson = JSON.parse(errText);
        if (errJson.body) { try { errMsg = JSON.parse(errJson.body).message || errMsg; } catch(e3) {} }
        else if (errJson.message) { errMsg = errJson.message; }
    } catch(e2) { if (errText) errMsg += ': ' + errText.substring(0, 200); }
    throw new Error(errMsg);
}
let res = await resp.json();
```

This throws into the existing `catch(e)` block which already renders errors with a Retry button.

## Correctness Properties

### Property 1: Error responses surface the actual error

For any non-200 HTTP response from the AI analysis endpoint, the `aiTimelineAnalysis()` function SHALL display the error message in the AI panel with a Retry button, rather than showing "No analysis returned."

### Property 2: Successful responses continue to render correctly

For any 200 HTTP response with a valid analysis object (with or without Lambda proxy envelope), the function SHALL continue to parse, unwrap, and render all analysis sections identically to the current behavior.

## Files Changed

| File | Change |
|------|--------|
| `src/frontend/investigator.html` | Add `resp.ok` check in `aiTimelineAnalysis()` function (~line 4452) |

## Testing Strategy

- Manual: Load timeline, click AI Analysis — verify loading spinner shows, then analysis renders (happy path)
- Manual: Simulate backend error (e.g., invalid case ID) — verify error message shows with Retry button
- Manual: Verify AbortController timeout still works (55s)
- Regression: Verify Lambda proxy envelope unwrapping still works for 200 responses
