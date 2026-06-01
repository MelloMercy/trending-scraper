import { useCallback, useEffect, useState } from "react";
import type { Region } from "@/lib/types";

function readRegion(): Region {
  const r = new URLSearchParams(window.location.search).get("region");
  return r === "intl" ? "intl" : "cn";
}

function writeRegion(region: Region) {
  const url = new URL(window.location.href);
  if (region === "intl") url.searchParams.set("region", "intl");
  else url.searchParams.delete("region");
  window.history.replaceState({}, "", url.toString());
}

/**
 * Region state synced bidirectionally with URL search param.
 * Updates body[data-region] for CSS hooks.
 */
export function useRegion(): [Region, (r: Region) => void] {
  const [region, setRegionState] = useState<Region>(readRegion);

  const setRegion = useCallback((r: Region) => {
    setRegionState(r);
    writeRegion(r);
    document.body.setAttribute("data-region", r);
  }, []);

  // initial body attribute + popstate listener
  useEffect(() => {
    document.body.setAttribute("data-region", region);
    const onPop = () => setRegionState(readRegion());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [region]);

  return [region, setRegion];
}
