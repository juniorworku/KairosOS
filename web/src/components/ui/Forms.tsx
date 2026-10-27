import {
  useState,
  useId,
  Children,
  isValidElement,
  cloneElement,
  type ReactNode,
  type FormEvent,
} from "react";
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
      typeof child.type === "string" &&
      ["input", "select", "textarea"].includes(child.type),
  );
  const id = isValidElement<{ id?: string }>(control)
    ? control.props.id || generated
    : generated;
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {Children.map(children, (child) =>
        isValidElement<{ id?: string; "aria-describedby"?: string }>(child) &&
        typeof child.type === "string" &&
        ["input", "select", "textarea"].includes(child.type)
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
    <p role="alert" className="error-note">
      {error instanceof Error ? error.message : c.requestFailed}
    </p>
  ) : null;
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="empty-state">
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
