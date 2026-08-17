"use client";

import { useRouter } from "next/navigation";

import FadeIn from "../animations/FadeIn";
import Button from "../ui/Button";

type ExperienceCardProps = {
  id: string;
  slug: string | null;
  title: string;
  recipient: string;
  // Raw backend status (ExperienceDraft.Status), used to decide the action —
  // never inferred from statusLabel, which is only for display.
  status: string;
  statusLabel: string;
  createdAt: string;
};

// Resume/access action per status. Every target here already exists and
// works today (CheckoutView already resumes checkout / shows the publish
// step based on payment status; /e/[slug] already renders a published
// experience; /experience/edit/[draftId] loads the draft's own data back
// into the wizard, see ExperienceContext's initialDraftId) — this only
// wires the Dashboard card into those routes, no new flow beyond that.
function getCardAction(
  status: string,
  id: string,
  slug: string | null
): { label: string; href: string } | null {
  switch (status) {
    case "draft":
      return { label: "Continuar edição", href: `/experience/edit/${id}` };
    case "awaiting_payment":
      return { label: "Continuar pagamento", href: `/checkout/${id}` };
    case "payment_failed":
      return { label: "Tentar pagamento novamente", href: `/checkout/${id}` };
    case "paid":
      return { label: "Publicar experiência", href: `/checkout/${id}` };
    case "published":
      return slug ? { label: "Abrir experiência publicada", href: `/e/${slug}` } : null;
    default:
      return null;
  }
}

export default function ExperienceCard({
  id,
  slug,
  title,
  recipient,
  status,
  statusLabel,
  createdAt,
}: ExperienceCardProps) {
  const router = useRouter();
  const action = getCardAction(status, id, slug);

  return (
    <FadeIn>
      <div
        className="
          rounded-3xl
          border
          border-white/10
          bg-white/5
          p-8
          backdrop-blur-xl
          transition-all
          duration-300
          hover:-translate-y-2
          hover:border-yellow-400/40
          hover:shadow-[0_0_40px_rgba(250,204,21,.15)]
        "
      >
        <div className="flex items-center justify-between">

          <span className="rounded-full bg-yellow-400/20 px-3 py-1 text-xs font-semibold text-yellow-300">
            {statusLabel}
          </span>

          <span className="text-xs text-slate-400">
            {createdAt}
          </span>

        </div>

        <h2 className="mt-6 text-2xl font-bold text-white">
          {title}
        </h2>

        <p className="mt-3 text-slate-400">
          Para {recipient}
        </p>

        {action && (
          <Button
            variant="secondary"
            className="mt-6 w-full py-3 text-sm"
            onClick={() => router.push(action.href)}
          >
            {action.label}
          </Button>
        )}

      </div>
    </FadeIn>
  );
}