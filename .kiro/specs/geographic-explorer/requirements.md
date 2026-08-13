# Geographic Explorer — Requirements

## Overview
A dedicated tab/view in the investigator frontend that lets users browse sites grouped by Country → Region → Individual Site, with taxonomy scores, field notes, and links to the map and graph views.

## User Stories

1. As an investigator, I want to filter all entities by country so I can focus my research on a specific geographic area.
2. As a field researcher, I want to see all sites in a country listed with their taxonomy scores so I can prioritize which to visit.
3. As an analyst, I want to drill into a site and see its deep research (mysteries, connections, field notes) without switching tabs.
4. As a trip planner, I want sites grouped by region within a country so I can plan driving routes.

## Requirements

### R1: Country List View
- Show all countries that have location entities in the current case
- Show count of sites per country
- Click a country to expand and see its regions

### R2: Region Grouping
- Within a country, group sites by region (e.g., "Boyne Valley", "Sligo", "Kerry Coast")
- Show count per region
- Collapsible/expandable

### R3: Site Card
Each site shows:
- Name, category, age/date built
- Top 3 taxonomy scores (which patterns it matches)
- Number of connections (edges) to other sites
- GPS coordinates (clickable → jumps to Map tab centered on that site)
- Field notes (from the research data)
- "Investigate" button → opens AI Investigator focused on that site

### R4: Cross-Domain Indicator
- Badge showing if a site is "cross-cutting" (matches 2+ taxonomy domains)
- Visual distinction between gold/high-relevance sites and standard ones

### R5: Integration
- Clicking a site pin on Map tab → opens the Geographic Explorer card for that site
- Clicking "Show on Map" in Geographic Explorer → switches to Map tab, centers on site
- Clicking "Graph" → shows network connections for that site in graph view

## Data Source
- Neptune nodes with `country` and `region` properties
- Local JSON data at `src/data/conspiracy-seed/irish_sacred_sites/`
- Taxonomy scores from `src/data/proof-engine-results-irish-sacred-sites.json`

## Priority
HIGH — needed for Ireland trip in 2 weeks
