# Bugfix Requirements Document

## Introduction

The AI Analysis button on the Investigative Timeline tab silently fails when the backend returns a non-200 HTTP status (e.g., 500 from a Bedrock timeout or service error). The `aiTimelineAnalysis()` function in `investigator.html` does not check `resp.ok` before parsing the response as JSON. When the API returns an error envelope, the function accesses `res.analysis` which is `undefined`, resulting in the panel displaying "No analysis returned" with no indication that an error occurred. The user sees no useful feedback and cannot distinguish between "no data" and "API failure."

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN the AI analysis API (`POST /case-files/{id}/timeline/ai-analysis`) returns a non-200 HTTP status (e.g., 500 from Bedrock timeout) THEN the system silently parses the error response body as JSON, accesses `res.analysis` which is `undefined`, and displays "No analysis returned. The AI may need more event data." — giving no indication that an error occurred.

1.2 WHEN the AI analysis API returns a 500 error with an error envelope (`{"statusCode": 500, "body": "{\"error\":...}"}`) THEN the system unwraps the Lambda proxy response and still attempts to read `.analysis` from the error payload, showing a misleading "no analysis" message instead of the actual error.

1.3 WHEN the Bedrock invocation times out or throws an exception on the backend THEN the system catches the `AbortError` from the 55-second client timeout but does NOT detect or surface the server-side 500 error that arrives before the client timeout fires.

### Expected Behavior (Correct)

2.1 WHEN the AI analysis API returns a non-200 HTTP status THEN the system SHALL detect the error via `resp.ok` check, extract the error message from the response body, and display a clear error message in the AI panel (e.g., "AI analysis failed: [error details]") with a Retry button.

2.2 WHEN the AI analysis API returns a 500 error envelope THEN the system SHALL parse the error message from the envelope and display it to the user, distinguishing between server errors and "no data" conditions.

2.3 WHEN the Bedrock invocation fails on the backend (timeout, throttling, model error) THEN the system SHALL surface the server-side error message to the user with actionable context (e.g., "AI analysis failed: Bedrock timeout. Try again — the Lambda is warmed up now.") and a Retry button.

### Unchanged Behavior (Regression Prevention)

3.1 WHEN the AI analysis API returns a 200 status with a valid analysis object THEN the system SHALL CONTINUE TO parse the response, extract the `analysis` object, and render all analysis sections (chronological patterns, escalation trends, clustering significance, gap interpretation, cross-entity coordination, recommended follow-ups) in the AI panel.

3.2 WHEN the AI analysis API returns a 200 status with a Lambda proxy envelope (`{"statusCode": 200, "body": "{...}"}`) THEN the system SHALL CONTINUE TO unwrap the envelope and render the analysis correctly.

3.3 WHEN the user clicks AI Analysis with no timeline events loaded (`tlEvents.length === 0`) THEN the system SHALL CONTINUE TO show the toast "Load timeline first" and not make an API call.

3.4 WHEN the client-side 55-second AbortController timeout fires before any response arrives THEN the system SHALL CONTINUE TO display the "AI analysis timed out" message with a Retry button.

3.5 WHEN the AI analysis API returns a 200 status but the analysis object has no keys THEN the system SHALL CONTINUE TO display "No analysis returned. The AI may need more event data."
