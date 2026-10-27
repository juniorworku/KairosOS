export function cleanDomains(values: string[]): string[] {
  return [...new Set(values.map((v) => v.trim().toLowerCase()))].filter(
    (v) =>
      v.length <= 253 &&
      /^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/.test(v) &&
      !["localhost", "127.0.0.1"].includes(v),
  );
}
export function makeRules(
  domains: string[],
  redirect: boolean,
): chrome.declarativeNetRequest.Rule[] {
  return cleanDomains(domains)
    .slice(0, 100)
    .map((domain, i) => ({
      id: 1000 + i,
      priority: 1,
      action: redirect
        ? {
            type: chrome.declarativeNetRequest.RuleActionType.REDIRECT,
            redirect: {
              extensionPath: "/blocked.html?d=" + encodeURIComponent(domain),
            },
          }
        : { type: chrome.declarativeNetRequest.RuleActionType.BLOCK },
      condition: {
        requestDomains: [domain],
        resourceTypes: [chrome.declarativeNetRequest.ResourceType.MAIN_FRAME],
      },
    }));
}
export function remaining(endsAt: string | null, now = Date.now()): number {
  return endsAt ? Math.max(0, Math.ceil((Date.parse(endsAt) - now) / 1000)) : 0;
}
