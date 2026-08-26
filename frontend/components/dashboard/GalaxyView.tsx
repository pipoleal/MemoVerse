"use client";

import DashboardShell from "@/components/dashboard/DashboardShell";
import GalaxyHub from "@/components/dashboard/GalaxyHub";
import { useGalaxyData } from "@/components/dashboard/useGalaxyData";

export default function GalaxyView() {
  const { drafts, loading, error } = useGalaxyData();

  return (
    <DashboardShell>
      <GalaxyHub drafts={drafts} loading={loading} error={error} />
    </DashboardShell>
  );
}
