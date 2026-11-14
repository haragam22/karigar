---
name: Karigar jewellery workbench
description: A restrained showroom for real jewellery and traceable workshop numbers.
colors:
  paper: "#FAFAF7"
  paper-2: "#F0EFE9"
  paper-3: "#E6E3DA"
  ink: "#1C1B19"
  ink-2: "#444139"
  muted: "#6C665B"
  rule: "#D8D3C8"
  accent: "#E2B04A"
  accent-ink: "#1C1B19"
  focus: "#926715"
  card: "#F5F3ED"
  field: "#24231F"
  field-muted: "#C5BFB1"
  field-rule: "#514C41"
  success: "#346347"
  success-bg: "#E5EDE5"
  error: "#A1352B"
  error-bg: "#F8E9E4"
  warn: "#775A1C"
  warn-bg: "#F3E9CF"
  transparent: "transparent"
typography:
  display:
    fontFamily: "Sentient, Georgia, serif"
    fontSize: "4.75rem"
    fontWeight: 300
    lineHeight: 0.98
    letterSpacing: "-0.018em"
  headline:
    fontFamily: "Sentient, Georgia, serif"
    fontSize: "2.986rem"
    fontWeight: 300
    lineHeight: 1.1
    letterSpacing: "-0.018em"
  title:
    fontFamily: "Sentient, Georgia, serif"
    fontSize: "1.728rem"
    fontWeight: 300
    lineHeight: 1.05
  body:
    fontFamily: "Hanken, system-ui, sans-serif"
    fontSize: "1rem"
    lineHeight: 1.55
  label:
    fontFamily: "Hanken, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 600
rounded:
  control: "4px"
  badge: "3px"
  card: "12px"
spacing:
  2xs: "4px"
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "24px"
  xl: "40px"
  2xl: "64px"
  3xl: "96px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.accent-ink}"
    rounded: "{rounded.control}"
    padding: "8px 16px"
    height: "44px"
  button-secondary:
    backgroundColor: "{colors.transparent}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "8px 16px"
  field:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "12px"
  status:
    backgroundColor: "{colors.paper-2}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.badge}"
    padding: "4px 8px"
  studio-canvas:
    backgroundColor: "{colors.field}"
    textColor: "{colors.paper}"
    rounded: "{rounded.card}"
---

# Design System: Karigar jewellery workbench

## Overview

**Creative North Star: "The showroom workbench"**

The showroom workbench puts the actual jewellery beside its measured gold. Atelier-derived serif typography and warm, sparse surfaces provide showroom luxury; familiar controls and tabular figures keep this an Operate-mode tool.

Visual ambition comes from the engine-generated object: a real GLB where available, with the actual render as poster or fallback. The interface keeps the customer’s Hinglish request, assumptions and numeric sources visible.

**Key Characteristics:**
- Object-led composition with a dark jewellery stage.
- Quiet warm surfaces, gold actions and ink navigation.
- Serif headings, sans controls and tabular measurements.

This document records the built console, extracted from `console/app.css`, `tokens.css`, `base.css`, `index.html` and `app.js`, and checked against studio screenshots at 1440px and 360px. The independent frontend review reported approval for the local sample-data demo at those widths. This documentation is not production or all-phase certification. App overrides are authoritative over the inherited Atelier defaults; unused inherited decorative tokens are intentionally omitted.

## Colors

### Primary
Gold is the action and active-navigation accent. Ink text sits on gold; gold is not the default body-text color. Focus uses the darker focus token.

### Neutral
Warm white is the page and input surface. The second and third paper tones provide quiet hover, loading and disabled layers. Ink and secondary ink carry content; muted carries help and source text. Rule is for dividers; actual field strokes use muted. Field, field-muted and field-rule support the dark rail and object stage.

Success, error and warning pairs are semantic support colors, not extra brand accents. Transparent is used by quiet controls. Card is an available app surface token; current main sections rely chiefly on open page space and rules.

**The Evidence Rule.** Sources, timestamps, assumptions and sample labels remain readable beside the numbers they qualify.

## Typography

Local Sentient (`sentient.woff2`, weight 300) is the display face, with Georgia and serif fallbacks. Local Hanken (`hanken.ttf`, variable 100–900) is the body face, with system-ui and sans-serif fallbacks. The runtime family is Hanken, not the inherited Hanken Grotesk name.

Display is reserved for the studio empty state and login statement. Page headings use the headline role; section headings use title. Smaller serif headings use 1.44rem, line-height 1.2. The working sans scale is 0.75, 0.875, 1, 1.2 and 1.44rem. Body line-height is 1.55; labels and controls use 0.875rem. Headings use light weight and tight tracking; table figures, quotes and weights use tabular numerals. Body/source lines generally cap at 65ch and the brief at 55ch. The inherited 1.2-based scale is supplemented by larger page/display sizes.

## Layout

Desktop uses a fixed 220px ink rail, 40px workspace gutters and a 1600px content constraint. The studio pairs a 1.4:1 object/brief grid with 40px gap; inspection splits use 1.5:1 and the showroom 2:1. The studio model is 500px tall; the standalone viewer is 600px. Three-column variant and catalogue grids sit on open surfaces. Every fifth leading catalogue piece spans two columns on wide screens. Standard tables retain a 620px minimum width inside a scrolling wrapper, with a phone scroll hint; numeric columns align right.

At ≤1200px the rail becomes 190px, gutters 24px, studio stage 460px, page type 2.488rem and display 3.8rem; catalogue becomes two columns. At ≤960px the rail becomes a full-width header with a Menu disclosure and two-column navigation; detail/viewer splits stack. At ≤650px gutters become 16px, page type 2.074rem, studio and variant/catalogue grids stack, stage height becomes 360px and standalone viewer height 420px. The real object stays before the brief. Process steps become two columns, forms stack, footer stacks, and the topbar sync control is hidden. At ≥1820px the overall workspace is centered with the rail aligned to it. Base CSS also includes 60rem/40rem inherited layout adjustments; app rules control the console's effective layout.

The spacing vocabulary is compact (4–16px) within controls, comfortable (24px) between related blocks, and open (40–96px) at major boundaries. Do not substitute inherited landing-page section gaps for working-console density.

## Elevation & Depth

Surfaces are primarily flat: warm tonal changes, hairline dividers and the dark object stage establish depth. The jewellery itself supplies dimensionality. The only applied UI shadow is the toast's 0 8px 24px ink shadow mixed to 16% opacity. The inherited decorative card shadow is not used by current console components.

Micro hover transitions use 120ms with cubic-bezier(0.16, 1, 0.3, 1); pressed buttons move down 1px. Model rotation is an explicit viewer control with pressed state and a pause label. Reduced-motion CSS shortens animations and transitions to 0.01ms and disables smooth scrolling; it does not itself certify GLB rotation behavior.

## Shapes

Controls and navigation have restrained 4px corners; status badges use 3px. Object stages, images and chat messages use 12px corners. Thin rules separate sections and table rows. These are functional, modest surfaces rather than ornamental frames.

## Components

### Buttons
Primary actions use gold with ink text, 8px 16px padding and a minimum 44px height. Hover mixes gold 85% with paper. Secondary buttons are transparent with a rule border; quiet buttons remove the visible border. Both hover toward paper-2. Disabled buttons use paper-3 and muted with a wait cursor. Pressed controls shift 1px down. All focusable controls receive a 2px focus outline with 2px offset.

### Inputs / Fields
Native text inputs, selects and textareas use warm-white fill, a 1px muted stroke, 4px corners and 12px padding; controls are at least 44px tall. Textareas start at 125px and resize vertically. Keep visible labels and helper text; search and inline refinement retain accessible visually hidden labels. Validation and request failures use adjacent alert text rather than an invented invalid-field style.

### Navigation
Eight hash destinations retain the order Design studio, Orders, Design catalogue, 3D showroom, Gold rate, Workshop, Try in Hinglish, System. The ink rail uses muted light labels; hover uses the field surface with paper text. Gold and ink mark `aria-current`; order detail maps to Orders. At the mobile disclosure, preserve `aria-expanded` and `aria-controls`, and close the menu on route change. A skip link becomes visible on keyboard focus. Breadcrumbs identify the sample workshop when sample records are present.

### Status chips
Compact text badges use neutral paper-2/ink-2 by default. Done, pass and current use success; fail, failed and infeasible use error; warn, solved, queued and running use warning. The text remains the authoritative status. Needs-info uses the neutral treatment and a human-readable label.

### Cards / Containers
Variant cards are open image-and-text blocks separated by a bottom rule, with 12px image corners. A selected variant darkens its rule and selection button. Chat uses paper-2 messages and ink user messages; the studio has a dark stage with real GLB, poster and caption. Do not assume a universal boxed-card component.

### Object stage and measurements
Use the bundled model-viewer for drag, pinch and scroll inspection, with camera controls and meaningful alt text. Reset and explicit automatic-rotation controls accompany the showroom. Keep engine-generated weights and quote totals in tabular figures. Quote sources wrap anywhere, including long URLs. Missing render/model states state what is unavailable and offer creation when relevant; viewer load failures produce explanatory status text.

### Loading, empty, error and persistence
Loading uses paper-2, muted text and a 140px minimum block; the initial shell announces opening through a status region. Empty states use a concise heading, explanation and optional action. Failures stay in the order view or adjacent alert, while action/refresh feedback uses the ink toast with polite live status. Warning notices preserve clarifying questions and assumptions. Queued work remains visible when the worker is offline.

Owner access lives in sessionStorage and is removed on sign-out; catalogue-start briefs also use a session draft, cleared after creation. Route-local field values, open details and model-camera state are remembered in memory during re-renders. Five-second polling avoids replacing active inputs, textareas and selects while editing; a pending update renders on a subsequent eligible refresh after focus leaves the field. Chat is held in runtime state. These are tab/session affordances, not durable cross-device storage guarantees.

## Do's and Don'ts

### Do:
- **Do** retain the pinned ink, gold and warm-white palette.
- **Do** use real engine GLBs and renders with meaningful descriptions.
- **Do** keep sources, timestamps, assumptions and sample-data labels visible.
- **Do** preserve native controls, keyboard focus and in-progress input.

### Don't:
- **Don't** replace actual jewellery with decorative placeholder imagery.
- **Don't** turn every section into a shadowed card.
- **Don't** use status color without its text label.
- **Don't** imply that local demo review certifies production or every project phase.
