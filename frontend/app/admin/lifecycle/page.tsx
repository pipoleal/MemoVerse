import LifecycleView from "@/components/admin/LifecycleView";

// Mesmo motivo de app/admin/page.tsx: force-dynamic precisa estar num
// Server Component (ignorado silenciosamente em "use client").
export const dynamic = "force-dynamic";

export default function AdminLifecyclePage() {
  return <LifecycleView />;
}
