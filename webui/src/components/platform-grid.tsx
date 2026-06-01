import { PlatformCard } from "@/components/platform-card";
import type {
  AggregateGroup,
  PlatformTrendingResponse,
  Region,
} from "@/lib/types";
import type { PerPlatformData } from "@/hooks/use-trending-data";

interface PlatformGridProps {
  perPlatform: PerPlatformData[];
  groups: AggregateGroup[];
  region: Region;
  onDateChange: (platformId: string, payload: PlatformTrendingResponse) => void;
}

export function PlatformGrid({
  perPlatform,
  groups,
  region,
  onDateChange,
}: PlatformGridProps) {
  return (
    <div className="grid gap-5 [grid-template-columns:repeat(auto-fit,minmax(420px,1fr))]">
      {perPlatform.map((row) => (
        <PlatformCard
          key={row.platform.id}
          platform={row.platform}
          data={row.latest}
          history={row.history}
          region={region}
          groups={groups}
          onDateChange={onDateChange}
        />
      ))}
    </div>
  );
}
