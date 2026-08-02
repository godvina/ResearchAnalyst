# Requirements Document

## Introduction

An interactive Celestial Alignment Viewer for the UVG Grid Investigation dashboard (grid-globe.html) that visualizes how ancient sites on the UVG grid align to constellations and celestial bodies. The viewer overlays star maps onto the Leaflet geographic map, provides a precession time slider spanning 26,000 BCE to present, offers a split-view comparing rendered night sky with geographic site positions, and calculates quantified alignment significance. All astronomical calculations use real RA/Dec coordinates with proper precession math (50.3 arcseconds/year). Star catalog data is embedded inline within the single-file HTML frontend. Data sources include the existing uvg-grid-scored-findings.json with astronomical encoding signatures (am-gge-cnp-002).

## Glossary

- **Alignment_Viewer**: The top-level interactive UI component that renders celestial alignment visualizations within the UVG Grid Investigation dashboard
- **Star_Map_Overlay**: A translucent layer rendered on the Leaflet geographic map showing constellation patterns with stars positioned at geographic coordinates mirroring their celestial positions
- **Precession_Engine**: The calculation module that computes axial precession offsets for any given epoch using the rate of 50.3 arcseconds per year relative to J2000.0
- **Split_View**: A dual-panel layout with a rendered night sky on the left and the geographic map on the right, connected by alignment lines
- **Alignment_Search**: The search interface that queries scored findings data to locate sites matching a specified constellation pattern within angular precision thresholds
- **Star_Catalog**: The embedded inline dataset containing RA/Dec coordinates for stars in supported constellations (Orion, Draco, Pleiades, Sirius, Southern Cross)
- **Constellation_Pattern**: A set of star positions defining a constellation's recognizable shape (e.g., three stars of Orion's Belt)
- **Deviation_Metric**: The calculated distance in kilometers between a star's projected geographic position and the actual ancient site position
- **Epoch**: A specific point in time used for precession calculations, expressed as a year (e.g., 10500 BCE, 2000 CE)
- **Gnomonic_Projection**: The mathematical projection that maps celestial RA/Dec coordinates onto geographic lat/lng positions relative to a projection center
- **Angular_Precision**: The angular difference in degrees between a constellation pattern overlay and actual site positions
- **Significance_Calculator**: The module that computes the probability of an alignment occurring by random chance using Monte Carlo or combinatorial methods
- **Sky_Renderer**: The D3.js-based component that renders a night sky view for a given date, time, and observer location
- **Solstice_Line**: A line on the geographic map showing the azimuth of sunrise or sunset at solstice or equinox for a specific site and epoch

## Requirements

### Requirement 1: Star Map Overlay on Geographic Map

**User Story:** As a research analyst, I want constellation patterns overlaid on the geographic map as translucent layers, so that I can visually compare star positions to ancient site locations.

#### Acceptance Criteria

1. WHEN a user enables a constellation overlay, THE Star_Map_Overlay SHALL render the selected Constellation_Pattern on the Leaflet map as translucent polylines connecting star positions
2. THE Star_Map_Overlay SHALL position each star at geographic coordinates computed by the Gnomonic_Projection from the star's RA/Dec coordinates relative to a user-specified or auto-detected projection center
3. THE Star_Map_Overlay SHALL display each star as a labeled circle marker with the star's name and visual magnitude represented by marker size
4. WHEN the Star_Map_Overlay is visible, THE Alignment_Viewer SHALL display the Deviation_Metric in kilometers between each projected star position and the nearest ancient site within 500 kilometers
5. THE Star_Map_Overlay SHALL render at 40% opacity by default so that underlying map features and site markers remain visible
6. WHEN a user toggles the Star_Map_Overlay off, THE Alignment_Viewer SHALL remove all constellation polylines and star markers from the Leaflet map

### Requirement 2: Precession Time Slider

**User Story:** As a research analyst, I want a time slider that shifts constellation alignments according to Earth's axial precession, so that I can identify which historical epochs produce the closest alignment between stars and sites.

#### Acceptance Criteria

1. THE Alignment_Viewer SHALL display a horizontal time slider with a range from 26000 BCE to 2025 CE, with 100-year step increments
2. WHEN a user moves the Precession Slider to a new Epoch, THE Precession_Engine SHALL recalculate all star positions by applying the precession offset of 50.3 arcseconds per year relative to J2000.0
3. WHEN the Precession_Engine recalculates star positions, THE Star_Map_Overlay SHALL update all projected geographic coordinates and Deviation_Metrics in real time without requiring a page reload
4. THE Alignment_Viewer SHALL display the currently selected Epoch in a label adjacent to the slider in the format "YYYY BCE" or "YYYY CE"
5. WHEN the Deviation_Metric for any star-to-site pair drops below 10 kilometers, THE Alignment_Viewer SHALL highlight that pair with a gold indicator and label it as "locked alignment"
6. THE Precession_Engine SHALL apply precession corrections to Right Ascension and Declination independently using the standard IAU precession formula simplified to the linear rate

### Requirement 3: Split-View Sky and Earth

**User Story:** As a research analyst, I want a side-by-side view showing the night sky and the geographic map simultaneously, so that I can compare celestial patterns with terrestrial site arrangements.

#### Acceptance Criteria

1. WHEN a user activates Split_View mode, THE Alignment_Viewer SHALL display a left panel containing the Sky_Renderer and a right panel containing the Leaflet geographic map, each occupying 50% of the available width
2. THE Sky_Renderer SHALL render a circular star field showing visible constellations for the currently selected Epoch, observer latitude/longitude (defaulting to the centroid of the active site cluster), and a midnight observation time
3. THE Split_View SHALL draw connecting lines from each star in the left panel to its corresponding projected geographic position in the right panel, using color-coded lines (green for deviation under 1 degree, yellow for 1 to 3 degrees, red for over 3 degrees)
4. WHEN a user changes the selected Epoch via the Precession Slider, THE Sky_Renderer SHALL update the rendered sky to reflect precession-adjusted star positions for that Epoch
5. WHEN a user clicks a site marker in the right panel, THE Sky_Renderer SHALL re-center the observer location to that site's coordinates and re-render the sky view
6. THE Split_View SHALL display aggregate Angular_Precision as a numeric value (in degrees) for the active constellation-to-site-cluster comparison

### Requirement 4: Alignment Search

**User Story:** As a research analyst, I want to search for all sites that align to a specific constellation, so that I can discover new potential astronomical correlations in the UVG grid data.

#### Acceptance Criteria

1. WHEN a user enters a constellation name in the Alignment_Search input, THE Alignment_Search SHALL query the scored findings data (uvg-grid-scored-findings.json) for sites with astronomical encoding signatures (am-gge-cnp-002) matching the specified constellation
2. THE Alignment_Search SHALL return results ranked by Angular_Precision, with the closest alignments listed first
3. WHEN results are returned, THE Alignment_Viewer SHALL draw the matched Constellation_Pattern over the geographic positions of the returned sites on the Leaflet map
4. THE Alignment_Search SHALL display for each result: site name, Angular_Precision in degrees, Deviation_Metric in kilometers, and the optimal Epoch at which alignment is closest
5. WHEN the user selects a search result, THE Alignment_Viewer SHALL zoom the Leaflet map to the selected site and activate the Star_Map_Overlay for the corresponding constellation at the optimal Epoch
6. IF no sites match the searched constellation within 5 degrees of Angular_Precision, THEN THE Alignment_Search SHALL display a message stating no significant alignments were found

### Requirement 5: Multi-Constellation Support

**User Story:** As a research analyst, I want support for multiple constellations and solar alignment lines, so that I can investigate diverse astronomical correlations across the UVG grid.

#### Acceptance Criteria

1. THE Star_Catalog SHALL contain RA/Dec coordinates (J2000.0 epoch) for all primary stars in: Orion (7 stars including Belt), Draco (15 stars), Pleiades (7 sisters), Sirius (1 star), and Southern Cross (4 stars)
2. THE Star_Catalog SHALL store for each star: name, RA in decimal hours, Dec in decimal degrees, and apparent visual magnitude
3. WHEN multiple constellations are enabled simultaneously, THE Star_Map_Overlay SHALL render each constellation in a distinct color with labeled constellation names
4. THE Alignment_Viewer SHALL compute and display Solstice_Lines showing summer solstice sunrise azimuth, winter solstice sunrise azimuth, and equinox sunrise azimuth for any selected site and Epoch
5. WHEN a Solstice_Line is enabled, THE Alignment_Viewer SHALL draw a ray from the site position along the computed azimuth extending 50 kilometers on the Leaflet map
6. THE Alignment_Viewer SHALL allow the user to add custom constellation definitions by specifying a set of RA/Dec coordinate pairs and a pattern name

### Requirement 6: Precession Calculation Precision

**User Story:** As a research analyst, I want mathematically precise precession calculations using real astronomical data, so that alignment conclusions are scientifically credible.

#### Acceptance Criteria

1. THE Precession_Engine SHALL compute precession-adjusted RA for a given Epoch using the formula: RA_adjusted = RA_J2000 + (precession_rate_RA × years_from_J2000), where precession_rate_RA is derived from the 50.3 arcseconds/year general precession applied to the ecliptic-to-equatorial coordinate transform
2. THE Precession_Engine SHALL compute precession-adjusted Dec for a given Epoch using the standard obliquity-dependent formula accounting for the star's ecliptic latitude
3. THE Gnomonic_Projection SHALL convert RA/Dec to geographic lat/lng using the formula: lat = Dec_adjusted, lng = (RA_adjusted × 15) - 180, normalized to the projection center
4. THE Precession_Engine SHALL produce positions for Orion's Belt stars at Epoch 10500 BCE that place the projected pattern within 2 degrees of the Giza pyramid complex when using Giza as the projection center
5. THE Alignment_Viewer SHALL display all angular values with a precision of 0.01 degrees (two decimal places)
6. THE Precession_Engine SHALL handle epoch inputs as signed integers where negative values represent BCE years (e.g., -10500 for 10500 BCE) and positive values represent CE years

### Requirement 7: Dynamic Alignment Generation

**User Story:** As a research analyst, I want alignment views auto-generated when I drill down on a site with astronomical signatures, so that I can immediately see which constellation aligns and how precisely.

#### Acceptance Criteria

1. WHEN a user clicks a site marker on the Leaflet map that has an astronomical encoding signature (am-gge-cnp-002) in the scored findings data, THE Alignment_Viewer SHALL automatically activate and display the relevant constellation overlay for that site
2. THE Alignment_Viewer SHALL determine the relevant constellation by parsing the site's signature evidence text for constellation names from the Star_Catalog
3. WHEN auto-generating an alignment view, THE Alignment_Viewer SHALL sweep the Precession Slider across all epochs in 500-year steps and identify the Epoch with minimum aggregate Deviation_Metric for the site-constellation pair
4. THE Alignment_Viewer SHALL display the auto-generated view with the optimal Epoch pre-selected on the Precession Slider and the Deviation_Metric prominently shown
5. WHEN auto-generation completes, THE Alignment_Viewer SHALL display a summary panel stating: constellation name, optimal Epoch, aggregate Angular_Precision, and whether the alignment qualifies as "locked" (deviation under 10 kilometers for primary pattern stars)
6. IF a site has no astronomical encoding signature, THEN THE Alignment_Viewer SHALL not auto-activate when the site marker is clicked

### Requirement 8: Quantified Alignment Significance

**User Story:** As a research analyst, I want to see the statistical probability of an alignment being random, so that I can assess whether a celestial correlation is meaningful or coincidental.

#### Acceptance Criteria

1. WHEN an alignment is displayed (manually or auto-generated), THE Significance_Calculator SHALL compute the probability that the observed angular precision occurred by random chance
2. THE Significance_Calculator SHALL use a Monte Carlo simulation with 10000 random site placements within the UVG grid bounding box to estimate the probability of N sites matching a Constellation_Pattern within the observed Angular_Precision threshold
3. THE Significance_Calculator SHALL display the result in the format: "N sites matching [constellation] within [X]° by random chance: 1 in [Y]" where Y is rounded to the nearest integer
4. WHEN the computed probability is less than 1 in 1000, THE Significance_Calculator SHALL label the alignment as "Statistically Significant" with a green indicator
5. WHEN the computed probability is between 1 in 100 and 1 in 1000, THE Significance_Calculator SHALL label the alignment as "Notable" with a yellow indicator
6. WHEN the computed probability is greater than 1 in 100, THE Significance_Calculator SHALL label the alignment as "Inconclusive" with a grey indicator
7. THE Significance_Calculator SHALL complete the Monte Carlo simulation within 3 seconds for a constellation of up to 7 stars matched against up to 62 sites

### Requirement 9: UI Integration with Dashboard

**User Story:** As a research analyst, I want the Celestial Alignment Viewer integrated seamlessly into the existing UVG Grid Investigation dashboard, so that I can access alignment tools without leaving the main interface.

#### Acceptance Criteria

1. THE Alignment_Viewer SHALL render within the existing grid-globe.html file as a collapsible panel below the Leaflet map, following the same layout pattern as the existing D3 network graph panel
2. THE Alignment_Viewer SHALL be activated via a toggle button labeled "🌌 Celestial Alignments" in the dashboard header navigation alongside existing buttons
3. WHEN the Alignment_Viewer panel is collapsed, THE dashboard SHALL display the standard map view without any celestial overlay elements
4. THE Alignment_Viewer SHALL load all JavaScript inline within grid-globe.html without requiring additional script file imports beyond the existing Leaflet.js and D3.js CDN references
5. THE Star_Catalog data SHALL be embedded as a JavaScript object literal within the HTML file, containing coordinates for all supported constellations (total data size under 5 KB)
6. WHEN the Alignment_Viewer is active, THE dashboard SHALL continue to display site markers, network graph edges, and sidebar intelligence panels without interference

### Requirement 10: Data Source Integration

**User Story:** As a research analyst, I want the alignment viewer to use existing scored findings data, so that astronomical correlations already identified by the AI research chain are immediately available.

#### Acceptance Criteria

1. THE Alignment_Viewer SHALL read site data from uvg-grid-scored-findings.json at dashboard startup, the same data source used by the existing map and network graph
2. THE Alignment_Viewer SHALL identify astronomically relevant sites by filtering for entries containing signature ID "am-gge-cnp-002" (Astronomical Encoding)
3. THE Alignment_Viewer SHALL extract from each matching site entry: site name, geographic coordinates (lat/lng), constellation reference, researcher citation, and confidence level
4. WHEN the scored findings data contains a constellation reference for a site, THE Alignment_Viewer SHALL use that reference to auto-select the matching Constellation_Pattern from the Star_Catalog
5. THE Alignment_Viewer SHALL support the known astronomical correlations: Giza to Orion (Bauval 1994), Angkor to Draco (Hancock 1998), Teotihuacan to Orion (Harleston 1974), and Stonehenge to midsummer sunrise (Lockyer 1901)
6. IF the scored findings data file fails to load, THEN THE Alignment_Viewer SHALL display an error message and disable alignment functionality without affecting other dashboard features
