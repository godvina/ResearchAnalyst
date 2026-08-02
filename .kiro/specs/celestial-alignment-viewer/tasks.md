# Implementation Plan: Celestial Alignment Viewer

## Overview

Implement a client-side Celestial Alignment Viewer module within `src/frontend/grid-globe.html`. The module adds astronomical visualization to the UVG Grid Investigation dashboard: star map overlays on the Leaflet map, precession time slider, split-view sky/earth comparison, alignment search, and Monte Carlo significance calculations. All code is inline JavaScript with no backend or build system.

## Tasks

- [ ] 1. Add Star Catalog and Precession Engine
  - [ ] 1.1 Embed STAR_CATALOG inline data object
    - Add the `STAR_CATALOG` JavaScript object literal containing all 5 constellations (Orion 7 stars, Draco 15 stars, Pleiades 7 stars, Sirius 1 star, Southern Cross 4 stars) with RA/Dec/magnitude and pattern edge arrays
    - Place within a `<script>` section before closing `</body>` or in the existing script block
    - Include `belt` array for Orion and `pattern` arrays for all constellations
    - _Requirements: 5.1, 5.2, 9.4, 9.5_

  - [ ] 1.2 Implement PrecessionEngine functions
    - Implement `precessRA(ra_j2000_hours, dec_j2000_deg, epochYear)` using Lieske precession formula
    - Implement `precessDec(ra_j2000_hours, dec_j2000_deg, epochYear)` using obliquity-dependent formula
    - Implement `celestialToGeo(ra_hours, dec_deg, projCenter)` for gnomonic projection mapping RA/Dec to lat/lng
    - Implement `haversineKm(lat1, lng1, lat2, lng2)` for distance calculations
    - Ensure epoch 2000 returns identity (no offset), and epoch -10500 produces valid Giza-Orion alignment
    - _Requirements: 2.2, 2.6, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ]* 1.3 Write property tests for PrecessionEngine in `_runTests()`
    - **Property 1: Precession Reversibility** — verify `precessRA(ra, dec, 2000) === ra`
    - **Property 2: Epoch Monotonicity** — verify Orion Belt declination decreases as epoch moves toward -10500
    - **Property 3: Deviation Non-Negativity** — verify all deviation metrics >= 0
    - **Property 4: Projection Center Invariance** — verify star at projection center maps to projection center
    - **Property 6: Giza-Orion Validation** — verify epoch -10500 with Giza center produces < 2° deviation
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 1.4, 2.5**

- [ ] 2. Implement StarMapOverlay (Leaflet Integration)
  - [ ] 2.1 Create StarMapOverlay rendering functions
    - Create `celestialLayer = L.layerGroup()` for managing constellation markers
    - Implement `renderConstellation(constellationId, epoch, projCenter)` that projects stars via PrecessionEngine and draws circle markers (sized by magnitude) and constellation polylines (dashed, 40% opacity) on the Leaflet map
    - Implement `clearOverlay()` to remove all celestial markers from the map
    - Implement `computeDeviations(projectedStars, sites)` that calculates km distance between each projected star and nearest site within 500km
    - Star markers should show tooltip with name and magnitude on hover
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 2.3_

  - [ ] 2.2 Implement locked alignment detection
    - When any star-to-site deviation < 10km, highlight with gold indicator and "locked alignment" label
    - Add CSS class `.locked-alignment` with pulse animation
    - Display deviation metrics in the alignment metrics panel
    - _Requirements: 2.5_

- [ ] 3. Implement Celestial Panel UI and Precession Slider
  - [ ] 3.1 Add celestial panel HTML and CSS
    - Add collapsible `#celestialPanel` div below the Leaflet map (same layout pattern as network graph panel)
    - Add "🌌 Celestial Alignments" toggle button in the dashboard header nav alongside existing buttons
    - Add constellation selector dropdown (Orion, Draco, Pleiades, Southern Cross)
    - Add Split View toggle button
    - Add all CSS rules for `.celestial-panel`, `.celestial-header`, `.epoch-control`, etc.
    - _Requirements: 9.1, 9.2, 9.3, 9.6_

  - [ ] 3.2 Implement epoch slider and UI controller
    - Add range input `#epochSlider` with min=-26000, max=2025, step=100
    - Implement `updateEpoch(epochValue)` that recalculates all star positions and updates the map overlay in real time
    - Implement `openCelestialPanel()` and `closeCelestialPanel()` functions
    - Display epoch label in "YYYY BCE" or "YYYY CE" format
    - _Requirements: 2.1, 2.4_

- [ ] 4. Checkpoint - Verify core rendering works
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Implement Sky Renderer (Split View)
  - [ ] 5.1 Implement SkyRenderer with D3
    - Implement `renderSkyView(epoch, obsLat, obsLng)` that renders a circular sky chart using D3 SVG
    - Use stereographic projection to position stars within the sky circle based on altitude/azimuth for observer location
    - Draw sky background, compass labels (N/S/E/W), and star dots sized by magnitude
    - Draw constellation lines matching the active constellation's pattern array
    - _Requirements: 3.1, 3.2, 3.4_

  - [ ] 5.2 Implement split-view layout and connecting lines
    - Implement `toggleSplitView()` that splits layout into left (sky SVG) and right (Leaflet map) at 50% width each
    - Implement `drawConnectingLines()` that draws color-coded lines from sky panel stars to their geographic projections (green < 1°, yellow 1-3°, red > 3°)
    - When user clicks a site in the right panel, re-center observer to that site and re-render sky
    - Display aggregate Angular_Precision as numeric value
    - _Requirements: 3.1, 3.3, 3.5, 3.6_

- [ ] 6. Implement AlignmentSearch
  - [ ] 6.1 Implement findAlignedSites and findOptimalEpoch
    - Implement `findAlignedSites(constellationName)` that queries `scoredData.results` for sites with `am-gge-cnp-002` or `am-gge-xpat-002` signatures matching the constellation
    - Implement `findOptimalEpoch(site, constellationId)` that sweeps epochs in 500-year steps from -26000 to 2025, returning the epoch with minimum aggregate deviation
    - Implement `detectConstellation(text)` that parses text for constellation names from STAR_CATALOG
    - Return results sorted by Angular_Precision (closest first)
    - _Requirements: 4.1, 4.2, 4.4, 10.1, 10.2, 10.3, 10.4_

  - [ ] 6.2 Implement alignment search UI and result rendering
    - Implement `renderResults(matches)` to display results with site name, Angular_Precision, Deviation_Metric in km, and optimal Epoch
    - When user selects a result, zoom map to site and activate overlay at optimal epoch
    - Display "No significant alignments found" when no sites match within 5°
    - Draw matched constellation pattern over geographic positions of returned sites
    - _Requirements: 4.3, 4.5, 4.6_

- [ ] 7. Implement SignificanceCalculator
  - [ ] 7.1 Implement Monte Carlo significance computation
    - Implement `monteCarloSignificance(constellationId, matchedSites, observedPrecision)` with 10,000 trials
    - Generate random site placements on Earth's surface for each trial
    - Check if random sites match constellation pattern within observed precision threshold
    - Use chunked execution via `requestAnimationFrame` to avoid blocking UI (complete within 3 seconds)
    - _Requirements: 8.1, 8.2, 8.7_

  - [ ] 7.2 Implement significance display and labeling
    - Format result as "N sites matching [constellation] within [X]° by random chance: 1 in [Y]"
    - Label as "Statistically Significant" (green) when ≥ 1 in 1000, "Notable" (yellow) for 1 in 100-1000, "Inconclusive" (grey) for < 1 in 100
    - Render significance result in `#significanceResult` panel element
    - _Requirements: 8.3, 8.4, 8.5, 8.6_

  - [ ]* 7.3 Write property test for Monte Carlo convergence in `_runTests()`
    - **Property 5: Monte Carlo Convergence** — verify 10,000 trials result is within ±10% of 5,000 trials result for same inputs
    - **Validates: Requirements 8.2, 8.7**

- [ ] 8. Implement Dynamic Alignment Trigger and Data Integration
  - [ ] 8.1 Implement auto-alignment on site click
    - Hook into existing `showNodeBrief()` function to call `checkAutoAlignment(node)`
    - When a site with `am-gge-cnp-002` signature is clicked, auto-activate celestial panel
    - Detect constellation from evidence text, sweep epochs for optimal alignment, pre-select epoch
    - Display summary: constellation name, optimal epoch, angular precision, locked status
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [ ] 8.2 Implement data source integration and error handling
    - Read site data from existing `scoredData` (already loaded by dashboard)
    - Filter for entries with signature ID `am-gge-cnp-002` (Astronomical Encoding)
    - Extract site name, coordinates, constellation reference, researcher citation, confidence level
    - Support known correlations: Giza-Orion (Bauval 1994), Angkor-Draco (Hancock 1998), Teotihuacan-Orion (Harleston 1974), Stonehenge-midsummer (Lockyer 1901)
    - Handle missing scoredData gracefully with error message and disabled alignment functionality
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

- [ ] 9. Implement Solstice Lines and Custom Constellations
  - [ ] 9.1 Implement solstice/equinox azimuth lines
    - Compute summer/winter solstice sunrise azimuth and equinox sunrise azimuth for selected site and epoch
    - Draw rays from site position along computed azimuth extending 50km on Leaflet map
    - Allow user to toggle solstice lines on/off
    - _Requirements: 5.4, 5.5_

  - [ ] 9.2 Implement custom constellation support
    - Allow user to add custom constellation definitions by specifying RA/Dec coordinate pairs and pattern name
    - Store custom constellations in the same format as STAR_CATALOG entries
    - Render custom constellations with user-specified or auto-assigned color
    - _Requirements: 5.6_

- [ ] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- All code goes in a single file: `src/frontend/grid-globe.html`
- No build system, no TypeScript — all plain JavaScript
- Testing is via an inline `_runTests()` function callable from browser console
- Star catalog is ~3KB embedded inline data
- Monte Carlo uses chunked requestAnimationFrame (no Web Worker needed)
- Existing libraries (Leaflet.js, D3.js) are already loaded via CDN

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["1.3", "2.1", "3.1"] },
    { "id": 3, "tasks": ["2.2", "3.2"] },
    { "id": 4, "tasks": ["5.1", "6.1"] },
    { "id": 5, "tasks": ["5.2", "6.2", "7.1"] },
    { "id": 6, "tasks": ["7.2", "7.3", "8.1"] },
    { "id": 7, "tasks": ["8.2", "9.1"] },
    { "id": 8, "tasks": ["9.2"] }
  ]
}
```
