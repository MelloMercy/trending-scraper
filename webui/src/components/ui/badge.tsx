import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold tabular-nums",
  {
    variants: {
      variant: {
        default: "bg-panel-3 text-muted",
        success: "bg-success/[0.14] text-success",
        warning: "bg-warning/[0.14] text-warning",
        danger:  "bg-danger/[0.14] text-danger",
        primary: "bg-primary/[0.14] text-primary-strong",
        hot:     "bg-hot/[0.14] text-hot",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant, className }))} {...props} />;
}
