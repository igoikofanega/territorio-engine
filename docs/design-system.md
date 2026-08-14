---
name: Sovereign Analytics
colors:
  surface: '#f7f9fb'
  surface-dim: '#d8dadc'
  surface-bright: '#f7f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f6'
  surface-container: '#eceef0'
  surface-container-high: '#e6e8ea'
  surface-container-highest: '#e0e3e5'
  on-surface: '#191c1e'
  on-surface-variant: '#424656'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f3'
  outline: '#727687'
  outline-variant: '#c2c6d8'
  surface-tint: '#0054d6'
  primary: '#0050cb'
  on-primary: '#ffffff'
  primary-container: '#0066ff'
  on-primary-container: '#f8f7ff'
  inverse-primary: '#b3c5ff'
  secondary: '#565e74'
  on-secondary: '#ffffff'
  secondary-container: '#dae2fd'
  on-secondary-container: '#5c647a'
  tertiary: '#4b5a70'
  on-tertiary: '#ffffff'
  tertiary-container: '#63738a'
  on-tertiary-container: '#f6f8ff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dae1ff'
  primary-fixed-dim: '#b3c5ff'
  on-primary-fixed: '#001849'
  on-primary-fixed-variant: '#003fa4'
  secondary-fixed: '#dae2fd'
  secondary-fixed-dim: '#bec6e0'
  on-secondary-fixed: '#131b2e'
  on-secondary-fixed-variant: '#3f465c'
  tertiary-fixed: '#d3e4fe'
  tertiary-fixed-dim: '#b7c8e1'
  on-tertiary-fixed: '#0b1c30'
  on-tertiary-fixed-variant: '#38485d'
  background: '#f7f9fb'
  on-background: '#191c1e'
  surface-variant: '#e0e3e5'
typography:
  headline-xl:
    fontFamily: Hanken Grotesk
    fontSize: 36px
    fontWeight: '700'
    lineHeight: 44px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Hanken Grotesk
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Hanken Grotesk
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
  body-md:
    fontFamily: Hanken Grotesk
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-sm:
    fontFamily: Hanken Grotesk
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-caps:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
  mono-data:
    fontFamily: Geist
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 40px
  gutter: 20px
  margin-mobile: 16px
  margin-desktop: 32px
---

## Brand & Style

The design system is built for high-performance SaaS environments, emphasizing precision, clarity, and authority. It adopts a **Corporate / Modern** aesthetic, drawing inspiration from industry leaders like Stripe and Vercel. 

The brand personality is professional yet innovative, prioritizing information density without sacrificing legibility. The interface should feel "engineered"—every pixel has a purpose. We utilize generous whitespace to frame complex data visualizations, ensuring the user remains focused on insights rather than the interface itself. The emotional response should be one of confidence, reliability, and technological sophistication.

## Colors

The palette is centered on a high-contrast foundation to ensure peak readability for data-heavy dashboards.

- **Primary (Electric Blue):** Used strictly for action states, primary buttons, and critical data highlights. It is the "thread" that guides the user through the workflow.
- **Secondary (Deep Charcoal):** Reserved for primary headings and core navigation elements to provide a strong visual anchor.
- **Tertiary (Slate):** Used for body text, secondary labels, and icons to maintain a hierarchy that doesn't overwhelm the eye.
- **Neutral (Ghost White/Slate):** A range of greys used for backgrounds and subtle borders to create "zones" within the dashboard without using heavy lines.

For geographic heatmaps, use a progressive scale of the Primary Blue or a diverging Emerald-to-Amber scale for demographic performance metrics.

## Typography

This design system utilizes **Hanken Grotesk** for its clean, geometric construction and high legibility in corporate settings. It provides the "professional" weight required for a SaaS product. 

For technical data, coordinates, and metric values, we utilize **Geist**—a monospaced-leaning font that ensures numerical columns align perfectly and technical strings are easily parsable.

- **Headlines:** Use tight letter-spacing for large displays to create a sophisticated, editorial look.
- **Body:** Standardized on a 14px/16px base to allow for high information density.
- **Labels:** Uppercase labels in Geist should be used for table headers and overlines.

## Layout & Spacing

The system employs a **Fluid Grid** model with fixed-width sidebars for navigation and analytics controls.

- **Dashboard Layout:** A 12-column grid is used for the main content area. On desktop, the sidebar is fixed at 280px.
- **Rhythm:** We use a 4px baseline shift. All components should have padding and margins that are multiples of 4 (4, 8, 12, 16, 24, 32, 40).
- **Responsive Behavior:** 
  - **Desktop (1440px+):** 3-column widget layout for metrics.
  - **Tablet (768px - 1024px):** Sidebar collapses into a hamburger menu; 2-column widget layout.
  - **Mobile (<768px):** Single column stack with 16px horizontal margins.

## Elevation & Depth

To maintain a sleek, modern feel, this design system avoids heavy drop shadows. Instead, it uses **Tonal Layers** and **Refined Border Treatments**.

- **Level 0 (Background):** The base canvas uses the Neutral color (`#F8FAFC`).
- **Level 1 (Cards/Panels):** Pure white background with a 1px border in `#E2E8F0`. 
- **Level 2 (Dropdowns/Modals):** Subtle ambient shadow (0px 4px 12px rgba(15, 23, 42, 0.08)) and a slightly darker border to separate the element from the panel layer.
- **Interactive States:** On hover, cards may lift slightly with a subtle increase in shadow spread (0px 10px 20px rgba(15, 23, 42, 0.04)).

## Shapes

The shape language is "Rounded" to soften the industrial nature of the data. 

- **Base Components:** Buttons and Input fields use an 8px (`0.5rem`) radius.
- **Containers:** Dashboard widgets and main panels use a 16px (`1rem`) radius to create a distinct containerized look.
- **Interactive Elements:** Small tags or chips use a pill-shape (full radius) to differentiate them from actionable buttons.

## Components

### Buttons
- **Primary:** Solid Electric Blue background, white text. No gradient. 
- **Secondary:** White background, 1px Slate border, Slate text.
- **Ghost:** No background or border, used for utility actions (e.g., "Export").

### Inputs & Selects
- Use an 8px radius with a 1px Slate border. 
- On focus: Border changes to Primary Blue with a 3px soft blue outer glow (halo).
- Labels are always positioned above the input in `label-caps` typography.

### Data Chips
- Small, 24px high indicators. 
- Use semi-transparent backgrounds of the primary color (10% opacity) with high-contrast text for status indicators.

### Cards (Dashboard Widgets)
- White background, 16px rounded corners, 1px subtle border.
- Include a 16px internal padding (inset).
- Headers within cards should use a 1px bottom border to separate the title from the data visualization.

### Map Controls
- Floating glassmorphic controls (backdrop blur: 12px) with 50% white opacity.
- Icons should be 20px stroke-based (2px weight) for a crisp appearance.