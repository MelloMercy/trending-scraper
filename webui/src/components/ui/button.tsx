import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-sm text-sm font-medium transition-colors duration-150 ease-smooth disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:shadow-focus",
  {
    variants: {
      variant: {
        default:
          "bg-panel/80 text-fg border border-border hover:bg-panel-2 hover:border-border-strong",
        primary:
          "bg-primary text-bg hover:bg-primary-strong border border-transparent shadow-[0_10px_24px_hsl(var(--primary)/0.18)]",
        ghost:
          "bg-transparent text-muted hover:bg-panel hover:text-fg border border-transparent",
        outline:
          "bg-bg/20 text-fg border border-border-strong hover:bg-panel",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm:      "h-8 px-3",
        icon:    "h-9 w-9",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
