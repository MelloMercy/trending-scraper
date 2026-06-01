import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

interface CoverImageProps {
  src?: string | null;
  alt?: string;
  className?: string;
  fallback?: React.ReactNode;
  /** Gradient hue (HSL hue 0-360) when no image — derived from a key string for consistency */
  hueKey?: string;
}

/**
 * Image with graceful fallback. If `src` is null/empty or load fails, renders
 * a soft gradient placeholder (deterministic by `hueKey`).
 */
export function CoverImage({ src, alt, className, fallback, hueKey }: CoverImageProps) {
  const [errored, setErrored] = useState(false);
  // Reset error state when src changes
  useEffect(() => {
    setErrored(false);
  }, [src]);

  if (!src || errored) {
    const hue = hashHue(hueKey || alt || "x");
    return (
      <div
        className={cn(
          "flex items-center justify-center bg-panel-2",
          className
        )}
        style={{
          backgroundImage: `linear-gradient(135deg, hsl(${hue} 30% 22%), hsl(${(hue + 60) % 360} 30% 14%))`,
        }}
        aria-label={alt}
      >
        {fallback}
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={alt ?? ""}
      loading="lazy"
      decoding="async"
      onError={() => setErrored(true)}
      className={cn("object-cover", className)}
      referrerPolicy="no-referrer"
    />
  );
}

function hashHue(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h) % 360;
}
