# Chrome manual QA

Automated tests cover domain validation, rule IDs, navigation-only behavior, redirects, and expiry arithmetic. These checks require a manual unpacked-extension run and are not claimed complete:

- Pair, revoke, and verify revoked token cannot refresh state.
- Start with bridge configured; selected domains block within two seconds.
- Unrelated sites and non-navigation requests are not blocked.
- Restart service worker mid-session; state and alarms recover.
- Disconnect API; local deadline still removes rules.
- Pause five minutes, then resume only if session remains active.
- End early from popup and reminder page.
- Restart Chrome before and after deadline; check multiple windows.
- Deny optional host permission; basic blocking still works.
