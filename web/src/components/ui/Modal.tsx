import { Children, createElement, isValidElement, type ReactNode } from "react";
import { Dialog, DialogContent, DialogTitle } from "../primitives/dialog";

export function Modal({
  titleId,
  onClose,
  children,
}: {
  titleId: string;
  onClose: () => void;
  children: ReactNode;
}) {
  let hasTitle = false;
  const content = Children.map(children, (child) => {
    if (isValidElement<{ id?: string }>(child) && child.props.id === titleId) {
      hasTitle = true;
      // Let Radix own the title ID and aria-labelledby so screen-reader naming stays intact.
      const props = { ...child.props };
      delete props.id;
      return (
        <DialogTitle asChild>{createElement(child.type, props)}</DialogTitle>
      );
    }
    return child;
  });
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent
        className="modal max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-2xl overflow-y-auto"
        aria-describedby={undefined}
        onInteractOutside={(event) => event.preventDefault()}
      >
        {!hasTitle && <DialogTitle className="sr-only">Details</DialogTitle>}
        {content}
      </DialogContent>
    </Dialog>
  );
}
