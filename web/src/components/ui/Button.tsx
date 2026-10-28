import { forwardRef } from "react";
import {
  Button as PrimitiveButton,
  type ButtonProps,
} from "../primitives/button";
import { cn } from "../../lib/utils";

// Preserve the app's action classes while routing every legacy action through shadcn.
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className = "", variant, ...props }, ref) => {
    const classes = className.split(/\s+/);
    const action =
      variant ||
      (classes.includes("danger")
        ? "destructive"
        : classes.includes("primary")
          ? "default"
          : classes.includes("icon-button")
            ? "ghost"
            : "outline");
    return (
      <PrimitiveButton
        ref={ref}
        variant={action}
        className={cn("button", className)}
        {...props}
      />
    );
  },
);
Button.displayName = "Button";
