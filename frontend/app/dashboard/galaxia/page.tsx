"use client";

import DashboardShell from "@/components/dashboard/DashboardShell";
import GalaxyHub from "@/components/dashboard/GalaxyHub";
import { useDashboardData } from "@/components/dashboard/useDashboardData";

export default function GalaxyPage() {
  const { drafts, loading, error } = useDashboardData();

  return (
    <DashboardShell>
      <GalaxyHub drafts={drafts} loading={loading} error={error} />
    </DashboardShell>
  );
}
