# Technical Design: Celestial Alignment Viewer

## Overview

The Celestial Alignment Viewer is a client-side JavaScript module embedded inline within `src/frontend/grid-globe.html`. It adds astronomical visualization capabilities to the existing UVG Grid Investigation dashboard, enabling researchers to see how ancient sites align to constellations at different precessional epochs.

All computation runs in the browser. No backend changes required. Star catalog data (~3KB) is embedded as a JavaScript literal. The module integrates with the existing Leaflet map, D3.js library, and scored findings data.

## Architecture

```
grid-globe.html
├── Existing Components (unchanged)
│   ├── Leaflet Map (gridLayer, siteLayer, focusLayer)
│   ├── D3 Network Graph (networkPanel)
│   ├── Audio Player (audioPlayer)
│   └── Sidebar (intelligence briefs)
│
└── NEW: Celestial Alignment Module
    ├── STAR_CATALOG (inline data ~3KB)
    │   └── {orion, draco, pleiades, sirius, crux} with RA/Dec/mag
    │
    ├── PrecessionEngine (pure math)
    │   ├── precessRA(ra, dec, epochYears)
    │   ├── precessDec(ra, dec, epochYears)
    │   └── celestialToGeo(ra, dec, projCenter)
    │
    ├── StarMapOverlay (Leaflet layer)
    │   ├── constellationLayer (L.layerGroup)
    │   ├── renderConstellation(name, epoch, projCenter)
    │   ├── updateEpoch(newEpoch)
    │   └── computeDeviations(sites)
    │
    ├── SkyRenderer (D3 canvas)
    │   ├── renderSkyView(epoch, observerLat, observerLng)
    │   └── drawConnectingLines(starPositions, sitePositions)
    │
    ├── AlignmentSearch
    │   ├── findAlignedSites(constellationName)
    │   ├── findOptimalEpoch(site, constellation)
    │   └── renderResults(matches)
    │
    ├── SignificanceCalculator
    │   ├── monteCarloSignificance(pattern, sites, threshold, trials)
    │   └── formatProbability(hits, trials)
    │
    └── UI Components
        ├── celestialPanel (collapsible, below map)
        ├── precessionSlider (range input)
        ├── constellationSelector (dropdown)
        └── splitViewToggle (button)
```

## Component Designs

### 1. Star Catalog (STAR_CATALOG)

_Satisfies: Requirements 5.1, 5.2, 9.5_

Embedded inline JavaScript object. Each constellation contains an array of stars with J2000.0 coordinates and a `pattern` array defining which stars connect visually.

```javascript
var STAR_CATALOG = {
    orion: {
        name: "Orion",
        color: "#f6ad55",
        stars: [
            {name:"Alnitak", ra:5.679, dec:-1.943, mag:1.77},  // Belt left
            {name:"Alnilam", ra:5.603, dec:-1.202, mag:1.69},  // Belt center
            {name:"Mintaka", ra:5.533, dec:-0.299, mag:2.23},  // Belt right
            {name:"Betelgeuse", ra:5.919, dec:7.407, mag:0.42},
            {name:"Rigel", ra:5.242, dec:-8.202, mag:0.13},
            {name:"Bellatrix", ra:5.418, dec:6.350, mag:1.64},
            {name:"Saiph", ra:5.795, dec:-9.670, mag:2.09}
        ],
        belt: [0, 1, 2],  // Indices of belt stars (primary pattern)
        pattern: [[0,1],[1,2],[3,5],[5,0],[2,6],[6,4],[4,2]]  // Edge pairs
    },
    draco: { ... },  // 15 stars
    pleiades: { ... },  // 7 stars
    sirius: { ... },  // 1 star + Canis Major context
    crux: { ... }  // 4 stars
};
```

**Data size**: ~2.5 KB for all 5 constellations (34 stars total).

### 2. Precession Engine (PrecessionEngine)

_Satisfies: Requirements 2.2, 2.6, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

Pure mathematical functions. No side effects, no DOM access.

```javascript
// Core precession calculation
// epochYear: signed integer (-10500 = 10500 BCE, 2000 = 2000 CE)
// J2000.0 reference epoch = year 2000
function precessRA(ra_j2000_hours, dec_j2000_deg, epochYear) {
    var T = (epochYear - 2000) / 100;  // Centuries from J2000
    // Simplified Lieske (1979) precession in RA
    // General precession in longitude: 50.29" + 0.022"*T per year
    var psi_a = (5029.0966 + 2.22226*T - 0.000042*T*T) * T; // arcseconds
    var deltaRA = psi_a / (3600 * 15); // Convert arcsec → hours
    return ra_j2000_hours + deltaRA * Math.cos(dec_j2000_deg * Math.PI/180);
}

function precessDec(ra_j2000_hours, dec_j2000_deg, epochYear) {
    var T = (epochYear - 2000) / 100;
    // Obliquity change affects declination
    var eta_a = (2004.3109 - 0.85330*T - 0.000217*T*T) * T; // arcseconds
    var deltaDec = eta_a * Math.sin(ra_j2000_hours * 15 * Math.PI/180) / 3600;
    return dec_j2000_deg + deltaDec;
}
```

**Projection: Celestial → Geographic**

```javascript
// Convert precession-adjusted RA/Dec to geographic coordinates
// projCenter: {lat, lng} — the site we're projecting relative to
function celestialToGeo(ra_hours, dec_deg, projCenter) {
    // Direct mapping: Dec → Lat (declination maps to latitude)
    // RA → Lng requires scaling and centering
    var lat = dec_deg;  // Simplified: declination ≈ latitude for meridian transit
    var lng = (ra_hours * 15) - 180;  // 1 hour RA = 15° longitude
    
    // Apply gnomonic projection centered on the projection site
    // This rotates the celestial pattern to overlay the geographic site
    var dLat = lat - projCenter.lat;
    var dLng = lng - projCenter.lng;
    
    // Scale factor: constellation angular size → geographic size
    // Orion's Belt spans ~2.7° in the sky → we project at 1:1 scale
    return {
        lat: projCenter.lat + dLat,
        lng: projCenter.lng + dLng
    };
}
```

**Validation**: At epoch -10500 (10,500 BCE), Orion's Belt declination was approximately -1° to +1° (near celestial equator). Giza is at 30°N. The projection centers the pattern on Giza, so the Belt's relative geometry (2.7° span, slight angle) maps to the three pyramids' relative geometry.

### 3. Star Map Overlay (StarMapOverlay)

_Satisfies: Requirements 1.1-1.6, 2.3_

A Leaflet LayerGroup that renders constellation patterns on the geographic map.

```javascript
var celestialLayer = L.layerGroup();  // Added to map when viewer active

function renderConstellation(constellationId, epoch, projCenter) {
    celestialLayer.clearLayers();
    var c = STAR_CATALOG[constellationId];
    if (!c) return;
    
    var projectedStars = c.stars.map(function(star) {
        var ra = precessRA(star.ra, star.dec, epoch);
        var dec = precessDec(star.ra, star.dec, epoch);
        return celestialToGeo(ra, dec, projCenter);
    });
    
    // Draw star markers (size by magnitude)
    projectedStars.forEach(function(pos, i) {
        var star = c.stars[i];
        var radius = Math.max(3, 8 - star.mag * 2);
        L.circleMarker([pos.lat, pos.lng], {
            radius: radius,
            color: c.color,
            fillColor: '#fff',
            fillOpacity: 0.8,
            weight: 2
        }).bindTooltip(star.name + ' (mag ' + star.mag + ')')
          .addTo(celestialLayer);
    });
    
    // Draw constellation lines
    c.pattern.forEach(function(edge) {
        var a = projectedStars[edge[0]], b = projectedStars[edge[1]];
        L.polyline([[a.lat, a.lng], [b.lat, b.lng]], {
            color: c.color, weight: 1.5, opacity: 0.4, dashArray: '4,4'
        }).addTo(celestialLayer);
    });
    
    // Compute and show deviations to nearest sites
    computeDeviations(projectedStars, c);
}
```

### 4. Precession Slider UI

_Satisfies: Requirements 2.1, 2.4, 2.5_

```html
<div id="celestialPanel" class="celestial-panel" style="display:none;">
    <div class="celestial-header">
        <span class="celestial-title">🌌 Celestial Alignment Viewer</span>
        <select id="constellationSelect">
            <option value="orion">Orion's Belt</option>
            <option value="draco">Draco</option>
            <option value="pleiades">Pleiades</option>
            <option value="crux">Southern Cross</option>
        </select>
        <button id="splitViewBtn">Split View</button>
        <button class="celestial-close" onclick="closeCelestialPanel()">✕</button>
    </div>
    <div class="celestial-body">
        <div class="epoch-control">
            <span id="epochLabel">2000 CE</span>
            <input type="range" id="epochSlider" min="-26000" max="2025" 
                   value="2000" step="100" oninput="updateEpoch(this.value)">
            <span class="epoch-range">26,000 BCE ← → 2025 CE</span>
        </div>
        <div id="alignmentMetrics" class="alignment-metrics"></div>
        <div id="significanceResult" class="significance-result"></div>
    </div>
</div>
```

### 5. Sky Renderer (Split View)

_Satisfies: Requirements 3.1-3.6_

D3-rendered circular sky chart in an SVG element. Shows stars as dots with constellation lines, rotated for the observer's latitude and the selected epoch.

```javascript
function renderSkyView(epoch, obsLat, obsLng) {
    var svg = d3.select('#skySvg');
    svg.selectAll('*').remove();
    var size = 300;  // Diameter of sky circle
    svg.attr('viewBox', '0 0 ' + size + ' ' + size);
    
    // Draw sky background (dark circle)
    svg.append('circle').attr('cx', size/2).attr('cy', size/2)
       .attr('r', size/2 - 2).attr('fill', '#0a0f19').attr('stroke', '#4a5568');
    
    // Project stars using stereographic projection for the observer
    var activeConstellation = STAR_CATALOG[currentConstellation];
    activeConstellation.stars.forEach(function(star, i) {
        var ra = precessRA(star.ra, star.dec, epoch);
        var dec = precessDec(star.ra, star.dec, epoch);
        // Stereographic: altitude/azimuth → x,y in circle
        var alt = 90 - Math.abs(dec - obsLat);  // Simplified
        var az = (ra * 15 - obsLng) % 360;
        var r = (90 - alt) / 90 * (size/2 - 10);
        var x = size/2 + r * Math.sin(az * Math.PI/180);
        var y = size/2 - r * Math.cos(az * Math.PI/180);
        
        svg.append('circle').attr('cx', x).attr('cy', y)
           .attr('r', Math.max(2, 5 - star.mag))
           .attr('fill', '#fff');
    });
}
```

### 6. Alignment Search

_Satisfies: Requirements 4.1-4.6_

Queries the existing `scoredData` (already loaded by the dashboard) for sites with `am-gge-cnp-002` signatures, then pattern-matches constellation names in their evidence text.

```javascript
function findAlignedSites(constellationName) {
    if (!scoredData || !scoredData.results) return [];
    var results = [];
    
    scoredData.results.forEach(function(node) {
        var astroMatch = node.matches.find(function(m) {
            return m.signature_id === 'am-gge-cnp-002' || m.signature_id === 'am-gge-xpat-002';
        });
        if (!astroMatch) return;
        
        // Check if this site's evidence mentions the constellation
        var evidence = (astroMatch.evidence_excerpt || '').toLowerCase();
        var indicators = (astroMatch.matched_indicators || []).join(' ').toLowerCase();
        if (evidence.indexOf(constellationName.toLowerCase()) < 0 &&
            indicators.indexOf(constellationName.toLowerCase()) < 0) return;
        
        // Find optimal epoch via sweep
        var geoNode = allNodes.find(function(n) { return n.id === node.node_id; });
        if (!geoNode) return;
        
        var optimal = findOptimalEpoch(geoNode, constellationName);
        results.push({
            nodeId: node.node_id,
            siteName: getNodeLabel(geoNode),
            lat: geoNode.lat,
            lng: geoNode.lng,
            constellation: constellationName,
            optimalEpoch: optimal.epoch,
            deviation: optimal.deviation,
            confidence: astroMatch.confidence
        });
    });
    
    return results.sort(function(a, b) { return a.deviation - b.deviation; });
}
```

### 7. Significance Calculator

_Satisfies: Requirements 8.1-8.7_

Monte Carlo simulation running in a Web Worker (or main thread with chunked execution to avoid blocking).

```javascript
function monteCarloSignificance(constellation, matchedSites, observedPrecision) {
    var c = STAR_CATALOG[constellation];
    if (!c) return {probability: 1, label: 'Inconclusive'};
    
    var N = matchedSites.length;
    var trials = 10000;
    var hits = 0;
    var patternAngularSize = getPatternSize(c);  // degrees
    
    for (var t = 0; t < trials; t++) {
        // Generate N random points on Earth's surface
        var randomSites = [];
        for (var i = 0; i < N; i++) {
            randomSites.push({
                lat: Math.asin(Math.random() * 2 - 1) * 180 / Math.PI,
                lng: Math.random() * 360 - 180
            });
        }
        // Check if random sites match constellation pattern within threshold
        if (checkPatternMatch(c, randomSites, observedPrecision)) {
            hits++;
        }
    }
    
    var probability = hits / trials;
    var oneInY = probability > 0 ? Math.round(1 / probability) : trials;
    var label = oneInY >= 1000 ? 'Statistically Significant' :
                oneInY >= 100 ? 'Notable' : 'Inconclusive';
    var color = oneInY >= 1000 ? '#48bb78' : oneInY >= 100 ? '#ecc94b' : '#718096';
    
    return {probability, oneInY, label, color,
            text: N + ' sites matching ' + c.name + ' within ' + 
                  observedPrecision.toFixed(2) + '°: 1 in ' + oneInY};
}
```

### 8. Dynamic Alignment Trigger

_Satisfies: Requirements 7.1-7.6_

Hooks into the existing `showNodeBrief()` function. When a node with am-gge-cnp-002 is clicked, auto-activates the celestial viewer.

```javascript
// Injected into showNodeBrief():
function checkAutoAlignment(node) {
    if (!scoredData) return;
    var scored = scoredData.results.find(function(r) { return r.node_id === node.id; });
    if (!scored) return;
    
    var astroSig = scored.matches.find(function(m) {
        return m.signature_id === 'am-gge-cnp-002' || m.signature_id === 'am-gge-xpat-002';
    });
    if (!astroSig) return;
    
    // Determine constellation from evidence
    var text = (astroSig.evidence_excerpt || '') + ' ' + 
               (astroSig.matched_indicators || []).join(' ');
    var constellation = detectConstellation(text);
    if (!constellation) return;
    
    // Open celestial panel and render
    openCelestialPanel();
    document.getElementById('constellationSelect').value = constellation;
    
    // Sweep epochs to find best alignment
    var optimal = findOptimalEpoch(node, constellation);
    document.getElementById('epochSlider').value = optimal.epoch;
    updateEpoch(optimal.epoch);
    
    // Show significance
    var sites = findAlignedSites(constellation);
    var sig = monteCarloSignificance(constellation, sites, optimal.deviation);
    renderSignificance(sig);
}
```

## CSS Additions

```css
/* Celestial Alignment Panel */
.celestial-panel{height:320px;border-top:1px solid rgba(246,173,85,0.25);
    background:#0d1320;display:flex;flex-direction:column;flex-shrink:0}
.celestial-header{padding:6px 14px;background:rgba(16,24,40,0.95);
    border-bottom:1px solid rgba(246,173,85,0.12);display:flex;
    align-items:center;gap:10px}
.celestial-title{font-size:0.72rem;font-weight:700;color:#f6ad55}
.epoch-control{display:flex;align-items:center;gap:10px;padding:8px 14px}
#epochSlider{flex:1;accent-color:#f6ad55}
#epochLabel{font-size:0.8rem;font-weight:700;color:#ecc94b;min-width:90px}
.alignment-metrics{padding:8px 14px;font-size:0.7rem;color:#a0aec0}
.significance-result{padding:8px 14px;border-radius:6px;margin:0 14px;
    font-size:0.72rem}
.deviation-line{stroke-dasharray:3,3;stroke-opacity:0.6}
.locked-alignment{animation:pulse 1s infinite alternate}
@keyframes pulse{from{opacity:0.6}to{opacity:1}}
```

## Data Flow

```
1. Dashboard loads → scoredData populated (existing flow)
2. User clicks "🌌 Celestial Alignments" → celestialPanel shown
3. User selects constellation → renderConstellation() called
4. PrecessionEngine computes star positions for current epoch
5. celestialToGeo() projects stars onto geographic coordinates
6. Leaflet renders star markers + constellation lines on map
7. computeDeviations() calculates km distance to nearest sites
8. User drags epoch slider → updateEpoch() recalculates everything
9. "Locked alignment" detected when deviation < 10km
10. monteCarloSignificance() computes random-chance probability
```

## Integration Points

| Existing Component | Integration Method |
|---|---|
| Leaflet map | New layer group `celestialLayer` added/removed |
| Scored data | Read `scoredData.results` filtered by am-gge-cnp-002 |
| `showNodeBrief()` | Call `checkAutoAlignment(node)` at end |
| Header nav | Add "🌌 Celestial" button next to "🎧 Listen" |
| Network panel | Both can be open simultaneously (stacked vertically) |
| INLINE_XPAT_DATA | xpat-002 (Orion) triggers auto-alignment |

## Performance Considerations

- Star catalog: 34 stars × 3 properties = ~100 values (trivial)
- Precession calc: O(n) where n = stars in constellation (max 15)
- Epoch slider update: ~5ms per frame (34 precession calcs + 34 marker moves)
- Monte Carlo: 10,000 trials × 7 stars × distance calc = ~2s in modern browser
- No Web Worker needed for 10K trials — chunked requestAnimationFrame sufficient

## File Changes

| File | Change |
|------|--------|
| `src/frontend/grid-globe.html` | Add STAR_CATALOG, PrecessionEngine, StarMapOverlay, AlignmentSearch, SignificanceCalculator, UI panel HTML/CSS, integration hooks |

Single file change. No backend. No new dependencies.


## Components and Interfaces

### PrecessionEngine (Pure Functions)
```
Interface:
  precessRA(ra_j2000_hours: number, dec_j2000_deg: number, epochYear: number) → number
  precessDec(ra_j2000_hours: number, dec_j2000_deg: number, epochYear: number) → number
  celestialToGeo(ra_hours: number, dec_deg: number, projCenter: {lat, lng}) → {lat, lng}
  haversineKm(lat1, lng1, lat2, lng2) → number
```

### StarMapOverlay (Leaflet Integration)
```
Interface:
  renderConstellation(constellationId: string, epoch: number, projCenter: {lat, lng}) → void
  updateEpoch(epoch: number) → void
  computeDeviations(projectedStars: [{lat,lng}], sites: [{lat,lng,name}]) → [{starName, siteName, km}]
  clearOverlay() → void
```

### SkyRenderer (D3 Visualization)
```
Interface:
  renderSkyView(epoch: number, obsLat: number, obsLng: number) → void
  drawConnectingLines(skyPositions: [{x,y}], geoPositions: [{lat,lng}]) → void
```

### AlignmentSearch (Query Engine)
```
Interface:
  findAlignedSites(constellationName: string) → AlignmentResult[]
  findOptimalEpoch(site: {lat,lng}, constellationId: string) → {epoch, deviation}
  detectConstellation(text: string) → string | null

Type AlignmentResult:
  nodeId: number
  siteName: string
  lat: number
  lng: number
  constellation: string
  optimalEpoch: number
  deviation: number
  confidence: string
```

### SignificanceCalculator (Statistics)
```
Interface:
  monteCarloSignificance(constellationId: string, matchedSites: [{lat,lng}], observedPrecision: number) → SignificanceResult

Type SignificanceResult:
  probability: number
  oneInY: number
  label: "Statistically Significant" | "Notable" | "Inconclusive"
  color: string
  text: string
```

### UI Controller (DOM/Events)
```
Interface:
  openCelestialPanel() → void
  closeCelestialPanel() → void
  updateEpochUI(epochYear: number) → void
  checkAutoAlignment(node: GridNode) → void
  toggleSplitView() → void
```

## Data Models

### Star Catalog Entry
```
{
  name: string,           // Constellation name
  color: string,          // Hex color for rendering
  stars: [
    {name: string, ra: number, dec: number, mag: number}
  ],
  belt: number[],         // Indices of primary pattern stars (optional)
  pattern: number[][]     // Edge pairs [[0,1],[1,2],...] for drawing lines
}
```

### Alignment Result
```
{
  nodeId: number,
  siteName: string,
  lat: number,
  lng: number,
  constellation: string,
  optimalEpoch: number,   // Signed year (-10500 = 10500 BCE)
  deviation: number,      // Degrees
  deviationKm: number,   // Kilometers
  confidence: string,     // "strong" | "moderate" | "weak"
  researcher: string      // Citation
}
```

### Epoch State
```
{
  currentEpoch: number,       // Signed year
  projCenter: {lat, lng},     // Projection center site
  activeConstellation: string, // Current constellation ID
  projectedStars: [{lat, lng, name, mag}],
  deviations: [{starName, siteName, km, deg}],
  isLocked: boolean           // Any deviation < 10km
}
```

## Error Handling

| Error Case | Handling |
|---|---|
| Star catalog missing constellation ID | Return early, log to console, show "Constellation not found" in UI |
| Scored data not loaded | Disable alignment search, show "Data unavailable" message |
| Epoch out of range | Clamp to [-26000, 2025] |
| No sites match constellation | Show "No significant alignments found" message |
| Monte Carlo takes >3s | Stop at current trial count, display partial result with caveat |
| Projection produces lat > 90 or < -90 | Clamp coordinates to valid range |
| NaN from precession calc | Skip star, render remaining, log warning |

## Testing Strategy

Since this is a single-file frontend module with no build system:

1. **Manual verification**: Validate Giza-Orion alignment at 10,500 BCE produces deviation < 2°
2. **Console tests**: Embed `_runTests()` function that verifies:
   - `precessRA(5.603, -1.202, -10500)` produces expected value
   - `celestialToGeo()` with Giza center produces lat/lng near 30°N/31°E
   - `haversineKm(29.98, 31.13, 30.0, 31.5)` ≈ 40km
3. **Visual verification**: Toggle overlay at known epochs and confirm stars align with known sites
4. **Significance check**: Monte Carlo with 3 random points in Orion pattern should give ~1 in 14,000

## Correctness Properties

### Property 1: Precession Reversibility
`precessRA(ra, dec, 2000)` SHALL equal `ra` (identity at J2000.0 reference epoch). This validates the engine returns unchanged coordinates when no time offset is applied.
**Validates: Requirements 6.1, 6.2**

### Property 2: Epoch Monotonicity for Orion
As epoch moves from 2000 CE toward 10,500 BCE, Orion's Belt declination SHALL decrease monotonically (Belt moves toward celestial equator in the past), consistent with known precessional drift.
**Validates: Requirements 6.1, 6.4**

### Property 3: Deviation Non-Negativity
All computed Deviation_Metrics SHALL be ≥ 0 for any combination of star positions and site positions.
**Validates: Requirements 1.4, 2.5**

### Property 4: Projection Center Invariance
A star located at exactly the projection center's celestial coordinates SHALL project to the projection center's geographic coordinates (deviation = 0).
**Validates: Requirements 6.3**

### Property 5: Monte Carlo Convergence
The significance probability computed with 10,000 trials SHALL be within ±10% of the probability computed with 5,000 trials for the same inputs.
**Validates: Requirements 8.2, 8.7**

### Property 6: Giza-Orion Validation
At epoch -10500 with Giza (29.98°N, 31.13°E) as projection center, Orion's Belt stars SHALL project within 2° aggregate angular precision of the three Great Pyramids layout.
**Validates: Requirements 6.4, 7.5**
