import { useEffect, useState } from "react";
import { registerSW } from "virtual:pwa-register";
import { copy as c } from "../copy/en";
import { Button } from "../components/ui/Button";
import { Card, CardContent } from "../components/primitives/card";
interface InstallEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: string }>;
}
export function PwaPrompt() {
  const [update, setUpdate] = useState<
    ((reload?: boolean) => Promise<void>) | null
  >(null);
  const [install, setInstall] = useState<InstallEvent | null>(null);
  useEffect(() => {
    const refresh = registerSW({
      onNeedRefresh() {
        setUpdate(() => refresh);
      },
    });
    const listener = (event: Event) => {
      event.preventDefault();
      setInstall(event as InstallEvent);
    };
    window.addEventListener("beforeinstallprompt", listener);
    return () => window.removeEventListener("beforeinstallprompt", listener);
  }, []);
  return update ? (
    <Card className="pwa-prompt" role="status">
      <CardContent className="flex flex-wrap items-center gap-2 pt-6">
        <span>{c.pwa.update}</span>
        <Button onClick={() => void update(true)}>{c.pwa.reload}</Button>
        <Button onClick={() => setUpdate(null)}>{c.pwa.dismiss}</Button>
      </CardContent>
    </Card>
  ) : install ? (
    <Card className="pwa-prompt">
      <CardContent className="flex flex-wrap items-center gap-2 pt-6">
        <Button
          onClick={() =>
            void install
              .prompt()
              .then(() => install.userChoice)
              .then(() => setInstall(null))
              .catch(() => setInstall(null))
          }
        >
          {c.pwa.install}
        </Button>
        <Button onClick={() => setInstall(null)}>{c.pwa.dismiss}</Button>
      </CardContent>
    </Card>
  ) : null;
}
