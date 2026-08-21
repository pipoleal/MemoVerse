"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { fetchMe, type Me } from "@/lib/adminAuth";
import { getAccessToken } from "@/lib/storage";
import AdminAccessDenied from "@/components/admin/AdminAccessDenied";
import AdminChecking from "@/components/admin/AdminChecking";
import AdminShell from "@/components/admin/AdminShell";

type GuardState =
  | { status: "checking" }
  | { status: "forbidden" }
  | { status: "authorized"; me: Me };

// Único ponto de proteção de /admin/* — reaproveita o MESMO JWT/axios
// client já usado pelo resto do produto (lib/api.ts, lib/storage.ts):
// nenhum sistema de autenticação novo. Client-side de propósito: os tokens
// vivem em localStorage (ver lib/storage.ts), que o middleware do Next
// (que roda no edge, antes de qualquer JS de página) não enxerga — não há
// como fazer este guard funcionar via middleware sem migrar todo o app
// para cookies primeiro, fora de escopo aqui.
export default function AdminLayout({ children }: LayoutProps<"/admin">) {
  const router = useRouter();
  const [state, setState] = useState<GuardState>({ status: "checking" });

  useEffect(() => {
    let cancelled = false;

    if (!getAccessToken()) {
      router.replace("/login");
      return;
    }

    fetchMe()
      .then((me) => {
        if (cancelled) return;
        setState(me.is_superuser ? { status: "authorized", me } : { status: "forbidden" });
      })
      .catch(() => {
        // 401 (token inválido/expirado e refresh também falhou) já é
        // tratado globalmente pelo interceptor de lib/api.ts, que limpa os
        // tokens e redireciona para /login sozinho. Qualquer outro erro
        // aqui (rede, 5xx) é tratado como "sem permissão" por segurança —
        // o painel administrativo nunca renderiza em caso de dúvida.
        if (cancelled) return;
        setState({ status: "forbidden" });
      });

    return () => {
      cancelled = true;
    };
  }, [router]);

  if (state.status === "checking") return <AdminChecking />;
  if (state.status === "forbidden") return <AdminAccessDenied />;

  return <AdminShell me={state.me}>{children}</AdminShell>;
}
