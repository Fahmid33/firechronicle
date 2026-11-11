# FireChronicle design system

The visual standard for all future frontend implementation. Read with [AGENTS](../AGENTS.md), [FRONTEND_PLAN](FRONTEND_PLAN.md), [API_CONTRACT](API_CONTRACT.md) and [UI_REFERENCE](UI_REFERENCE.md). The [team rulebook](FireChronicle_FINAL_Team_Rulebook_Para_Brazil.pdf), Pará amendment v1.0, remains authoritative for science and contracts. Design roles below are presentation semantics, not new API enums.

## Intent and implementation boundary

An Earth-observation mission console: a large, readable map, precise controls, calm dark surfaces and compact scientific evidence. Cinematic character comes from geographic context, composition and typography. Avoid glowing borders, saturated gradients, glass blur, ornamental telemetry, speculative statistics and card grids that displace the map. Amazon styling does not imply coverage of the entire Amazon: analytics are Pará (`BR-PA`) only.

Use the existing Tailwind v4 CSS-first theme and shadcn/ui **Base UI + base-nova** primitives. Do not reinstall or replace them. Theme tokens, font mapping, global focus fallback and CSS reduced-motion behavior live in `src/app/globals.css`. Phase 2 now implements the four-route shell, responsive navigation/analysis panels, time/layer controls and honest pending-data states. The starter page is replaced. Quantitative map styles, hatching on actual data, complete calendar matrices and chart rendering remain specifications for later phases; see FRONTEND_PLAN for current scope.

## Color roles and CSS contract

The dark palette is the default in both `:root` and `.dark`, including portal surfaces; no light theme or theme toggle is defined. Keep existing shadcn variable names. New feature code uses semantic utilities such as `bg-background`, `bg-card`, `bg-surface-elevated`, `text-muted-foreground`, `text-status-estimated` and `border-input`, not repeated hex values.

| Role | CSS variable | Value / use |
| --- | --- | --- |
| Canvas | `--background` | `#08131D`, page and map surround |
| Primary text | `--foreground` | `#F1F5F7`, headings, values, labels |
| Main panel | `--card` | `#11212B`; `--sidebar` aliases this |
| Elevated surface | `--popover` | `#182C34`, tooltips, menus, inset surfaces |
| Divider | `--border` | `#2D414B`, quiet structural separation |
| Secondary text | `--muted-foreground` | `#A4B8BF`, axes, metadata, support text |
| Action / Amazon accent | `--amazon`, `--primary`, `--ring` | `#37B99A`; primary action uses midnight `--primary-foreground` text |
| Hotspot / estimated accent | `--hotspot` | `#F5A64B`, explicit data marks and estimated labels |
| Justified severe activity class | `--activity-severe` | `#E46A43`, only with supported classification and visible legend; not a default high-end ramp |
| Identifiable control edge | `--input` | `#6A858F`, controls needing an edge independent of panel contrast |
| Destructive / request error | `--destructive` | `#F28B91`, error text/icon; unrelated to activity magnitude |

`--card-foreground`, `--popover-foreground`, `--secondary-foreground` and `--accent-foreground` alias primary text. `--secondary`, `--muted` and `--accent` alias elevated surfaces. Sidebar foreground is secondary text; active sidebar text is primary text with a green indicator. Selection and focus green never mean high fire activity.

Status tokens: `--status-observed` = green; `--status-estimated` and `--status-provisional` = amber; `--status-unsupported` and `--status-not-processed` = secondary text. Pattern, icon and text distinguish shared hues. `--chart-1/2/3` alias observed/estimated/secondary text; `--chart-4=#8AB9CE` and `--chart-5=#C4AFDD` are optional explicitly named comparison series, never extra sensors or a quantitative ramp. Bind series by meaning, never array order.

Use opaque primary/secondary text on dark surfaces. The quiet divider is not sufficient to identify a standalone control: use `border-input`, a clear icon/label and the focus indicator. Do not place white text on green/amber filled buttons; use midnight text. Do not reduce essential text opacity to create hierarchy. Quantitative palette stops, scale limits and thresholds require actual data and approved scientific interpretation; brand tokens do not define them.

## Typography

Keep the already configured **Geist Sans** for interface/body and **Geist Mono** for IDs, coordinates and compact numeric metadata. The CSS maps `--font-sans` and `--font-heading` to `--font-geist-sans`, with system sans fallbacks; `--font-mono` maps to `--font-geist-mono`, with monospace fallback. No new font package/download is introduced. Preserve Pará accents. Use tabular numerals for aligned values, with explicit units outside the numeral.

| Role | Size / line height | Weight |
| --- | --- | --- |
| Page / Sensor Lab heading | 24 / 32 px (`text-2xl`) | 600 |
| Panel heading | 18 / 28 px (`text-lg`) | 600 |
| Section title / main body | 16 / 24 px (`text-base`) | 600 / 400 |
| Controls and compact body | 14 / 20 px (`text-sm`) | 500 / 400 |
| Axis tick, metadata, status | 12 / 16 px (`text-xs`) | 400–500 |
| Selected numeric readout | 28 / 36 px | 500, tabular numerals |

Use sentence case; uppercase only for short overlines/IDs with modest tracking (0.06em). No essential text below 12 px. Mobile prose/form fields use 16 px. Avoid giant hero numerals and metric cards unrelated to selection. Wrap long source names/IDs without truncating the only accessible copy.

## Grid, density and responsive layout

Tailwind's existing 4 px spacing unit is retained. Preferred spacing: 4, 8, 12, 16, 24, 32, 48 px (`1,2,3,4,6,8,12`). Panel padding 16–24 px; compact control gap 8 px; related label/value gap 4 px. Maintain `min-width: 0` on chart/map columns. No fixed page height that hides controls when zoomed.

Desktop target **1440 × 900**: 64 px top header; 72 px collapsed navigation (expanded 224 px); flexible map/workspace; 320 px analysis column; 16 px shell gutters/gaps. Reserve roughly 112 px below the map for compact time controls; detailed year × month calendar is expandable below or in a dedicated workspace panel. With the rail collapsed, the map gets over two-thirds of the central content width. Expanded navigation may overlay rather than compress the map below a useful size. Use CSS Grid for shell columns; charts/calendar share panel headers and insets. Sensor Lab is a separate navigation view, retaining geographic/time context and a clear return to explorer.

| Width | Treatment |
| --- | --- |
| `<640px` | Mobile: 56 px header, navigation in a sheet, map around 50svh with 320 px minimum when space permits; time controls then contextual content in document flow. Optional bottom sheet must leave map controls/attribution reachable. |
| `640–767px` (`sm`) | Wider mobile: same single-column priority, larger calendar viewport; no permanent sidebar. |
| `768–1023px` (`md`) | Tablet: 64 px navigation rail, dominant map, contextual analysis in a dismissible sheet; calendar/trends below. |
| `1024–1279px` (`lg`) | Compact desktop: 64 px rail, flexible map, optional 288 px analysis column; switch analysis to sheet if the map would be narrower than 480 px. |
| `1280–1535px` (`xl`) | Full target composition: 72/224 px nav, flexible map, 320 px analysis. |
| `≥1536px` (`2xl`) | Keep map growing; analysis may reach 360 px, prose stays around 65 characters per line. |

At short viewport heights, let document/panel content scroll; never crop time controls to preserve a cinematic map. Support safe-area insets and 200% text zoom. Page content reflows at 320 CSS px; inherently two-dimensional map/calendar may scroll in labeled local regions. No accidental whole-page horizontal scrolling.

## Surfaces, radii and elevation

One-pixel borders and opaque panels establish hierarchy. Main panels use `bg-card`; menus/sheets use `bg-popover`; nested detail may use elevated surface without another surrounding card. Use `rounded-sm` 4 px for dense calendar cells, `rounded-md` 6 px for compact controls, `rounded-lg` 8 px for standard controls/cards and `rounded-xl` 12 px for floating panels/dialogs. `--radius=0.5rem`; larger 16/20/24 px tokens are reserved for exceptional containers, not repeated cards. Pills are for short badges only.

Docked panels use no shadow. `shadow-panel` is `0 8px 24px rgb(0 0 0 / 16%)`; `shadow-overlay` is `0 16px 48px rgb(0 0 0 / 32%)`. Shadows communicate overlap, never scientific certainty. No glow or animated elevation. Modal backdrop may dim the map without blurring it.

## Component grammar

Keep Base UI behavior, slots and accessibility; use existing Nova component APIs, not Radix-specific assumptions. Do not edit every primitive to apply a theme already supplied by variables. Future feature usage must choose appropriate size/state classes explicitly; current Nova small defaults do not automatically meet touch sizing.

| Pattern | Style and behavior |
| --- | --- |
| Navigation | Lucide 18–20 px icons with labels; inactive secondary text, hover elevated surface, current item primary text plus 2 px green marker and `aria-current`. Collapsed icons retain accessible names and focus tooltips. Preserve selected area/time when moving to Sensor Lab. |
| Button | Primary green with midnight text, secondary elevated with primary text, ghost for tertiary controls. Prefer 40 px desktop and 44 px touch height. Avoid activity amber for generic actions. Icon buttons require names; disabled uses explicit state, no hover and no loss of essential explanatory text. |
| Select / input | Visible label, dark surface, `border-input`, 40/44 px target, selected value plus chevron, labeled popup groups. Day/night options follow the approved API, not an invented enum. Errors include text and icon. |
| Tabs | Underline or quiet inset segmented treatment; active text plus green indicator, not hue alone. Use Base UI keyboard behavior; use manual activation where automatic selection would trigger expensive requests. |
| Tooltip | Opaque elevated surface, primary text, 12–14 px type, 8–12 px padding, 6 px radius; pointer and focus support, Escape dismissal, viewport collision handling. Essential status/source is visible outside the tooltip. Interactive details belong in a popover/dialog. |
| Card / panel | Heading, optional short context/actions, content, provenance/limitations footer. Reuse header spacing across map detail, calendar and charts. No redundant nested card stacks. |

## Map controls, layers and legends

Use the official frozen IBGE polygon only. Dim outside-Pará context lightly and label the active study area; no outside analytic interaction. Boundary has a clear continuous stroke; selected block has an independent white/green outline and text identifier. Hover uses an outline without altering the quantitative fill. Border blocks disclose clipped support.

Compact vertical zoom/reset controls sit top-right, with accessible 44 px targets, separate from the contextual panel. Layer control sits top-left; legend bottom-left; scale and required attribution remain unobscured. Time controls sit below the map, not over its attribution. Provide a labeled supported-block selector/list as a keyboard alternative to pointer-only map selection. Unavailable geometry yields an honest unavailable state, never an approximate Pará polygon.

Layer menu separates basemap/context, actual reported points, observed aggregates, estimated **50 km** blocks and coverage. Historical estimates never become fabricated hotspot points or validated 10 km cells. Actual observed points retain source coordinates; 10 km observed summaries must be labeled. Do not stack opaque observed/estimated choropleths so their meaning becomes ambiguous; favor explicit layer selection or a labeled comparison view.

Every legend includes measurement/unit, period, source, data status, spatial scale and coverage caveat, with a linked provenance detail. Separate quantitative values from missing/status patterns. Use backend-supplied or scientifically reviewed domains/classification; show exact breakpoints, transform (if any), filtering and whether the scale changes with selection. Prefer a consistent domain for supported comparisons. Until a domain is approved, show labeled values/neutral outlines rather than decorative intensity. Never use “severe,” risk, intensity or certainty as a synonym for a high count. Enable `--activity-severe` only if an approved data-derived class justifies that wording and threshold.

## Scientific status grammar

Status describes evidence, not magnitude. Always pair pattern/line/icon with visible text. It remains distinct from hover, focus and selection. Exact backend statuses remain available in details; the table does not finalize unresolved wire mappings.

| Status | Badge / mark | Calendar and chart treatment |
| --- | --- | --- |
| Observed | Green text + solid-circle icon; **Observed · S-NPP** | Solid mark/line for actual S-NPP; quantitative calendar fill may use its approved count scale. |
| Estimated | Amber text + diagonal-stripe icon; **Estimated · historical extrapolation** | Consistent diagonal hatch over quantitative cells/blocks; dashed line and distinct marker. Always show model version and 50 km scale. |
| Provisional | Amber text + clock icon; **Provisional · NRT** | Dotted perimeter/line and clock marker; identify S-NPP NRT and its date. Do not make it look finalized. |
| Unsupported | Secondary text + slash icon; **Unsupported** | Crossed neutral cell/explicit gap with reason; no numeric fill/value. |
| Not processed | Secondary text + pending icon; **Not processed** | Dotted neutral outline and dash with written status; no inferred zero. |
| Missing / unknown coverage | Secondary text + question icon; explicit reason | Neutral no-value mark, distinguishable from a verified zero and from estimated hatching. Do not recast absent metadata as Unsupported. |

Values must identify status, source and period. Observed is not a claim of complete coverage or certainty. Keep `coverage_status` separate from prediction status; an estimate may be preliminary with unknown coverage. A numeric zero can be displayed only with usable observation evidence and the applicable label. `null` is rendered as a dash plus its actual state/reason, never `0` or a low-count color.

## Time Machine calendar

Rows are supported years; columns are Jan–Dec with persistent year/month headers. Keep all twelve month positions so gaps are meaningful. Coverage controls availability; do not promise the full archive. Mid-2002–2011 supported estimates are hatched. Mark the transition into available S-NPP observations in 2012 with a labeled divider; keep finalized observations and provisional NRT visually separate.

Cells use 4 px radius and at least 32 px desktop visual height with adequately separated targets; use 44 px touch targets. On small screens preserve a locally scrollable matrix or provide a month list; never shrink labels into illegibility. Selected month gets an outer ring/corner marker independent of fill. Hover/focus shows month, value or missing reason, status, source, coverage and scale. A keyboard implementation uses one roving tab stop, arrow-key cell movement and Enter/Space selection, with row/column labels and equivalent accessible month details. Optional daily drilldown appears only when supplied by the backend.

Keep count-domain legends explicit; missing, unsupported and unprocessed have separate swatches. No fabricated numeric ramp, locally normalized intensity without disclosure, interpolated months or arbitrary anomaly colors. Season-matched comparisons use comparable tiers; mixed-era comparisons require demonstrated calibration stability. Changing area updates calendar/trends; selecting month updates map/time state without displaying stale values under a new title.

## Charts and Sensor Lab

Use Recharts with semantic series binding, straight segments, approximately 2 px strokes and 3–4 px markers at selected/focused points. Avoid smoothed curves that imply unsupported behavior. Observed is solid, estimated dashed, provisional dotted; legends show line samples plus names. Raw MODIS, if shown for validation, is a separately labeled muted series, never added to VIIRS. Break at missing values (`connectNulls=false`) and at the historical/observed transition; no artificial bridge between eras.

Use secondary-text axis ticks, restrained decorative gridlines and visible units/period labels. Count axes normally start at zero; any justified alternate domain/transform must be explicit. No logarithmic ratios or uncertainty bands until conventions/validation are supplied. Tick density adapts to width without changing data. Tooltips/popovers list period, selected area, labeled value/unit/status/source and coverage/model scale where relevant; provide keyboard inspection and a data-table/text alternative, not hover alone.

Sensor Lab presents real held-out MODIS-based estimates against actual S-NPP and distinguishes the ratio baseline from the selected validated candidate. Metrics show evaluation period, geographic holdout, sample size and limitations. Seasonal median/IQR requires approved comparable backend summaries; empirical IQR is labeled as spread, not model confidence. No invented scores or bands. No-data state explains whether selection, processing, coverage or transport is blocking the chart.

## Loading, errors and provenance

Skeletons use existing `Skeleton` with muted surface and stable dimensions; never placeholder statistics. Set the updating region `aria-busy`; use a concise polite announcement once, not on every shimmer. Keep location/time controls available. Retained cached data must keep its original selection/period and an explicit updating label; otherwise show a skeleton rather than mislabel stale data.

Request errors show an error icon, descriptive text and retry action scoped to the failed panel. A network/server error is not Unsupported or zero coverage. Empty states distinguish “Select a supported block,” “Not processed,” “Unsupported,” “Coverage unknown” and “Request failed” using actual metadata; a missing official boundary is a blocker, not a synthetic fallback.

Keep a compact visible footer near values: status, period, source/spacecraft, scale and relevant coverage limitation. Expandable provenance includes available dataset/processing version, UTC acquisition time, model version, boundary version, canonical IDs and source links. Do not invent absent metadata; say unavailable. Essential coverage/extrapolation limits stay visible when details are closed. DEVELOPMENT / SYNTHETIC mode has a persistent shell banner and labels on standalone views/exports.

## Interaction, accessibility and motion

Hover changes surface or outline; active/pressed changes border/indicator, not data magnitude. Focus uses a solid 2 px green outline with 3 px offset, independent of the component's Nova ring. Preserve existing primitive focus behavior; choose `border-input` where needed. Never suppress focus without an equivalent. In high-contrast mode use system colors (`Highlight` for focus) and retain text/pattern meaning.

Use `--duration-fast` 120 ms for feedback, `--duration-normal` 180 ms for menus, `--duration-panel` 240 ms for sheets with `--ease-standard: cubic-bezier(0.2,0,0,1)`. Transition only color, opacity and modest transform, not `all`. No pulsing hotspot symbols, auto-playing time travel, animated counters, parallax or ornamental map flight. Map navigation defaults to a direct update or restrained user-triggered movement.

Target readable text contrast of 4.5:1 (3:1 for large text) and meaningful control/focus/graphic contrast of 3:1. Check actual composed states; decorative borders are deliberately quieter. Use visible labels, semantic landmarks/headings, meaningful accessible names, logical tab order, keyboard equivalents for map/chart inspection and focus restoration on sheets/dialogs. Controls target 40 px desktop/44 px touch; compact exceptions must meet minimum target size/spacing. Do not rely on red/green or a tooltip alone. Focused controls cannot be obscured by panels.

CSS already reduces animations/transitions and disables smooth scrolling under `prefers-reduced-motion`. Future Motion components must also use reduced-motion preferences, and MapLibre/Recharts must disable animated camera/chart interpolation explicitly; CSS does not control their JavaScript animations. No automatic animation is required to understand data. Check 200% zoom, 320 px reflow, keyboard-only use, touch, forced colors and reduced motion before calling a screen complete.

## Future implementation review

Use this document when building each planned phase. Review actual screenshots at 1440×900, tablet and mobile once screens exist. Verify controls/statuses in hover/focus/disabled/loading/error states, nullable values and the 2012 transition. Numeric legend ranges and API mappings remain subject to scientific/backend approval. This token update alone is not a visual or accessibility certification of unimplemented screens.

Verification on 11 November 2026: `npm run lint` and `npm run build` passed, including TypeScript and static generation. The installed Tailwind compiler resolved all existing CSS imports and generated 17 representative semantic utilities; Lightning CSS parsed the result. Local documentation links resolved. Calculated opaque-color contrast across canvas/panel/elevated surfaces: primary text ≥13.21:1, secondary text ≥7.03:1, green focus/action accent ≥5.91:1 and input edges ≥3.70:1; midnight text on the green button is 7.64:1. Rendered screen, assistive-technology and interaction checks remain future acceptance work.
