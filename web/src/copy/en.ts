export const copy = {
  brand: "Kairos",
  tagline: "A little intention. Meaningful progress.",
  nav: {
    today: "Today",
    goals: "Goals",
    plan: "Weekly plan",
    focus: "Focus",
    review: "Reflection",
    coach: "Coach",
    settings: "Settings",
  },
  foundation: "Foundation preview",
  foundationNote:
    "You’re exploring the first foundation of Kairos. Planning and account features will arrive in the next milestones.",
  greeting: "Make room for what matters.",
  intro:
    "Bring your ambitions into your everyday. One clear goal, one thoughtful plan, one focused session at a time.",
  today: "Your day, with intention",
  todaySub: "A quieter place to decide what deserves your attention.",
  dateOptions: { weekday: "long", month: "long", day: "numeric" } as const,
  start: "Explore your goals",
  viewPlan: "View weekly plan",
  emptyTitle: "Every meaningful week starts with a goal.",
  emptyBody:
    "Soon, you’ll turn a goal into a realistic plan and see your next steps here. For now, explore the space we’re building.",
  emptyLabel: "A fresh start",
  next: "THE KAIROS LOOP",
  loopHeading: "Big ambitions. Small, deliberate steps.",
  loop: [
    {
      title: "Find your direction",
      text: "Define a meaningful outcome and the reason behind it.",
      label: "01 / GOALS",
    },
    {
      title: "Make the time",
      text: "Build a realistic week around the life you already have.",
      label: "02 / PLAN",
    },
    {
      title: "Give it your attention",
      text: "Work on one thing, then notice what helps you move forward.",
      label: "03 / FOCUS & REFLECT",
    },
  ],
  intention: "PROTECT YOUR ATTENTION",
  intentionTitle: "Progress needs a little breathing room.",
  intentionBody:
    "A good plan leaves space for breaks, unexpected moments, and being human.",
  note: "Inspired by research on implementation intentions and time blocking.",
  unavailable: "Coming in a later milestone",
  back: "Back to today",
  roadmap: "What’s taking shape",
  pages: {
    goals: {
      title: "Give your ambition a direction.",
      description:
        "Define your outcome, why it matters, and the actions that will move you toward it.",
      milestone: "M2 · Goals & GPS wizard",
      items: [
        "Measurable goals and target dates",
        "Up to five practical actions per goal",
        "If-then plans for the obstacles you expect",
      ],
    },
    plan: {
      title: "Make a little room for your goals.",
      description:
        "A realistic weekly plan will connect your actions with the time you actually have.",
      milestone: "M4 · Weekly planning",
      items: [
        "Drafts built around your availability",
        "Clear reasons for every suggested block",
        "Review and approve before anything reaches your calendar",
      ],
    },
    focus: {
      title: "One thing. Your full attention.",
      description:
        "A simple timer will help you begin, stay present, and reflect on how the session felt.",
      milestone: "M6 · Focus sessions",
      items: [
        "Focus sessions linked to your goals",
        "A timer that keeps time across page visits",
        "An honest session log and optional self-rating",
      ],
    },
    review: {
      title: "Notice what moves you forward.",
      description:
        "Make space to reflect on your wins, your obstacles, and one useful adjustment for next week.",
      milestone: "M6–M7 · Progress & reflection",
      items: [
        "Progress check-ins with your own measures",
        "Transparent, deterministic trajectory feedback",
        "Weekly wins, misses, and adjustments",
      ],
    },
    coach: {
      title: "A thoughtful second perspective.",
      description:
        "Coaching will help you explore changes while you stay in control of your goals and calendar.",
      milestone: "M7 · Optional AI coaching",
      items: [
        "Practical suggestions grounded in your progress",
        "Optional AI with clear usage limits",
        "Your approval before applying any suggested change",
      ],
    },
  },
  settings: {
    title: "Make Kairos feel like yours.",
    description:
      "Appearance is available now. Profile, availability, and connected accounts follow in the next milestones.",
    appearance: "Appearance",
    themeLabel: "Color theme",
    light: "Light",
    dark: "Dark",
    system: "System",
    connections: "Connected accounts",
    google: "Google Calendar",
    notConnected: "Not connected",
    connectionNote:
      "Calendar consent and sign-in are not available in this foundation preview.",
    backend: "Development connection",
    checking: "Checking API…",
    online: "API is reachable",
    offline: "API is not running",
    retry: "Check again",
    privacy:
      "Your space is empty. No account, calendar, or productivity data has been collected.",
  },
  skip: "Skip to content",
  menu: "Open navigation",
  closeMenu: "Close navigation",
  made: "A calmer path from intention to action.",
  local: "Local development",
  noData: "No activity yet",
  current: "CURRENT BUILD",
  foundationTitle: "A considered foundation",
  foundationBody:
    "The essentials are in place. Next, we’ll add secure sign-in and your first goal.",
};
