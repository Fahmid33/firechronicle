# FireChronicle UI reference brief

Apply [DESIGN_SYSTEM](DESIGN_SYSTEM.md) to all future screens. References guide information layout and interaction, not scientific scope, API contracts or palette copying.

**Review basis — 11 November 2026:** Read official-source excerpts returned by Parallel web search for the sources linked below. No interactive application walkthrough, screenshot inspection or pixel-level visual audit was performed. Documented features are distinguished from proposed FireChronicle adaptations.

| Reference | Documented pattern | FireChronicle adaptation (design recommendation) |
| --- | --- | --- |
| [NASA Earthdata: NASA Worldview](https://www.earthdata.nasa.gov/news/feature-articles/data-tool-focus-nasa-worldview) | Map-led interface, layer selection, bottom timeline and date navigation; documented keyboard time stepping. | Make geographic context primary, place time directly below the map, group layer controls and keep selected period visible. Use a supported monthly calendar, not a claim of daily historical imagery. |
| [Global Forest Watch map](https://www.globalforestwatch.org/map?gfwfires=true) | Map content exposes layer groups, LEGEND and ANALYSIS sections, temporal filters and interpretive caveats alongside datasets. | Separate “what is visible” from “what this area means.” Use a compact contextual panel and accessible legend with caveats near values. Retain Pará-only validated selections; GFW's other datasets/alerts do not establish FireChronicle capabilities. |
| [Google Earth Engine: Panels and Layouts](https://developers.google.com/earth-engine/guides/ui_panels) | Official examples compose map widgets and chart panels, with map-click callbacks updating a chart. | Link block selection to calendar/trends and preserve area/time when opening Sensor Lab. Use one shared selection state and responsive panels; do not reproduce an editor or introduce Earth Engine as another backend. |

For polished scientific dashboards, study the general grammar of aligned tabular numbers, direct units, consistent axes, concise provenance and clear no-data states. This is a design recommendation, not a claim that an additional external dashboard was inspected. Favor density that supports a scientific question over decorative KPI tiles.

## Composition and interaction to carry forward

At 1440×900, use a compact header, collapsible left navigation, dominant map, 320 px contextual panel and connected bottom time controls. Calendar and charts share heading, spacing, status legend and provenance conventions. Sensor Lab is a separate view for actual held-out evidence. On tablet move analysis into a sheet; on mobile prioritize map → time → selected-area detail in a readable single column.

Carry over the reference patterns, then add FireChronicle's essential distinctions: solid Observed, hatched/dashed Estimated, dotted Provisional, explicit Unsupported/Not processed/missing, visible 50 km historical scale and no invented legend thresholds. A selected period and source should remain readable without opening a tooltip. Missing values never acquire a low-activity color or numeric zero. Outside-Pará basemap context never becomes supported analytics.

## Review once screens exist

Check that a user can identify location, period, source, status and scale; select a supported block; update time and see linked results; recover from missing data; and inspect provenance with keyboard or touch. Compare map prominence and panel readability at desktop/tablet/mobile sizes. Avoid glow, simulated live telemetry, unsupported drawing tools, copied branding and animation that implies evidence or certainty.
