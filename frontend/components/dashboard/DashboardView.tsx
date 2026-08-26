"use client";

import DashboardHeader from "@/components/dashboard/DashboardHeader";
import DashboardShell from "@/components/dashboard/DashboardShell";
import ExperienceSection from "@/components/dashboard/ExperienceSection";
import HeroActions from "@/components/dashboard/HeroActions";
import JourneyStats from "@/components/dashboard/JourneyStats";
import { useDashboardData } from "@/components/dashboard/useDashboardData";

export default function DashboardView() {
  const { drafts, loading, error } = useDashboardData();

  return (
    <DashboardShell>
      <div className="flex flex-col gap-14">
        <DashboardHeader />
        <HeroActions />
        <JourneyStats drafts={drafts} loading={loading} error={error} />
        <ExperienceSection drafts={drafts} loading={loading} error={error} />
      </div>
    </DashboardShell>
  );
}
