# Interface design

Kairos uses a black, white and neutral-gray theme with [shadcn/ui](https://ui.shadcn.com/docs/components) components. Dark is the default; saved light/system preferences remain available. The earlier Framer-inspired glass treatment is replaced by flat surfaces, subtle borders and clear typography.

The official new-york component sources live in `web/src/components/primitives`, with their MIT license alongside them. `web/components.json` records the registry configuration. Radix supplies dialog and mobile-sheet focus management. Shared adapters preserve existing button variants, form labels, validation and modal callers. Native selects preserve browser selection behavior. FullCalendar remains the week/day calendar engine, styled with the same monochrome tokens.

Semantic HSL tokens live in `web/src/styles.css`; layout and page treatments live in `web/src/design.css`, with calendar rules in `web/src/features/agenda.css`. Tailwind utilities use those tokens. Status is communicated through labels, icons and border treatment. Reduced-motion preferences are honored. Cards, alerts, progress, skeletons, inputs and dialogs share the component system across Today, Goals, Plan, Focus, Review, Coach, Settings and sign-in.

The mobile navigation uses a focus-trapping Sheet with keyboard dismissal and focus restoration. Metric cards use shrinkable columns and compact mobile spacing to prevent horizontal overflow. The icon and install surfaces use the same black-and-white identity.

Users and invitation screens remain outside the personal app scope. `/admin/*` redirects to Today without removing authentication or accounts. No deployment is part of this refresh.
