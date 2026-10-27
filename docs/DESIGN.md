# Interface design

The October 2026 refresh follows the owner’s Framer reference direction while keeping Kairos’s own components and copy.

References:
- [Framer](https://www.framer.com/)
- [Framer template marketplace](https://www.framer.com/marketplace/templates/)
- [Glassy Style Layout](https://www.framer.com/marketplace/components/appleglassstack/) for layered surfaces, restrained blur, borders, and hover treatment.

No template was purchased, no Framer account was created, and no third-party component source or imagery was copied. The implementation remains native React/CSS with reusable metric cards, week overview, empty-state symbols, a floating sidebar, and a focus dial driven by the actual server deadline.

Manrope Variable is self-hosted through the pinned Fontsource package under OFL-1.1. The style layer is `web/src/design.css`; structural component styles remain in `web/src/styles.css`. Light/dark themes have separate surface and metric-card color tokens. Reduced-motion preferences disable decorative motion. Values and progress always come from saved data; decorative rings do not represent activity.

User administration is outside the current interface scope. The old `/admin` route redirects to Today, and the Users/invites UI is removed without deleting accounts or weakening authentication.
