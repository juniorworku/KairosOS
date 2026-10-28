import {
  useState,
  useId,
  Children,
  isValidElement,
  cloneElement,
  type ReactNode,
  type FormEvent,
} from "react";
import { CircleDashed, AlertCircle } from "lucide-react";
import { Label } from "../primitives/label";
import { Alert, AlertDescription } from "../primitives/alert";
import { copy as c } from "../../copy/en";
export function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}) {
  const generated = useId();
  const controls = Children.toArray(children);
  const control = controls.find(
    (child) =>
      isValidElement<{ id?: string }>(child) &&
      (typeof child.type !== "string" ||
        ["input", "select", "textarea"].includes(child.type)),
  );
  const id = isValidElement<{ id?: string }>(control)
    ? control.props.id || generated
    : generated;
  return (
    <div className="field">
      <Label htmlFor={id}>{label}</Label>
      {Children.map(children, (child) =>
        isValidElement<{ id?: string; "aria-describedby"?: string }>(child) &&
        (typeof child.type !== "string" ||
          ["input", "select", "textarea"].includes(child.type))
          ? cloneElement(child, {
              id: child.props.id || id,
              "aria-describedby": hint
                ? `${id}-hint`
                : child.props["aria-describedby"],
            })
          : child,
      )}
      {hint && <small id={`${id}-hint`}>{hint}</small>}
    </div>
  );
}

export function Notice({ error }: { error: unknown }) {
  return error ? (
    <Alert variant="destructive" className="error-note">
      <AlertCircle className="size-4" aria-hidden="true" />
      <AlertDescription>
        {error instanceof Error ? error.message : c.requestFailed}
      </AlertDescription>
    </Alert>
  ) : null;
}
export function Empty({
  title,
  children,
  icon,
}: {
  title: string;
  children?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="empty-state-symbol" aria-hidden="true">
        {icon || <CircleDashed size={28} strokeWidth={1.4} />}
      </span>
      <p>{title}</p>
      {children}
    </div>
  );
}
export function SubmitForm({
  onSubmit,
  children,
  className = "",
}: {
  onSubmit: () => Promise<void>;
  children: (busy: boolean) => ReactNode;
  className?: string;
}) {
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(undefined);
    setBusy(true);
    try {
      await onSubmit();
    } catch (error) {
      setError(error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className={className} onSubmit={(e) => void submit(e)}>
      <Notice error={error} />
      {children(busy)}
    </form>
  );
}
