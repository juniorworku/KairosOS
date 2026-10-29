# Interface design

Kairos uses warm neutral surfaces, muted lavender for planning and green for recorded progress with [shadcn/ui](https://ui.shadcn.com/docs/components) components. Warm light is the default. Visible light/dark controls in the sidebar and mobile bar persist the choice; Settings also retains a system preference. A self-hosted pre-paint script applies saved appearance without weakening CSP. The earlier Framer-inspired glass treatment is replaced by flat surfaces, subtle borders and clear typography.

The official new-york component sources live in `web/src/components/primitives`, with their MIT license alongside them. `web/components.json` records the registry configuration. Radix supplies dialog and mobile-sheet focus management. Shared adapters preserve existing button variants, form labels, validation and modal callers. Native selects preserve browser selection behavior. FullCalendar remains the week/day calendar engine, styled with the same semantic color tokens.

Semantic HSL tokens live in `web/src/styles.css`; layout and page treatments live in `web/src/design.css`, with calendar rules in `web/src/features/agenda.css`. Tailwind utilities use those tokens. Status is communicated through labels, icons and border treatment. Reduced-motion preferences are honored. Cards, alerts, progress, skeletons, inputs and dialogs share the component system across Today, Goals, Plan, Focus, Review, Coach, Settings and sign-in.

The mobile navigation uses a focus-trapping Sheet with keyboard dismissal and focus restoration. Metric cards use shrinkable columns and compact mobile spacing to prevent horizontal overflow. The icon and install surfaces use a restrained neutral identity.

Users and invitation screens remain outside the personal app scope. `/admin/*` redirects to Today without removing authentication or accounts. No deployment is part of this refresh.

## Connected workflow

Superfocus’s public product illustrations are the primary workflow reference. Today leads with the next accepted action or running session, then the real agenda, due tasks, seasonal pace and feedback. The calendar keeps date/goal/block context in the URL, shows actual working hours and combines draft additions, moves and removals in one review. A running-session strip stays reachable across screens. Focus completion offers an explicit outcome check-in and the corresponding weekly review. Coaching uses visible evidence and explicit sharing consent; text recommendations never mutate the calendar automatically.

Lavender, green, warm local-event and slate Google-event tints reinforce status; labels and border treatment retain meaning without color. Both light and dark themes share these semantic tokens.
