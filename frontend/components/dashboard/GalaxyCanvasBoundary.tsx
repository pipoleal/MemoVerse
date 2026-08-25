"use client";

import { Component, type ReactNode } from "react";

type GalaxyCanvasBoundaryProps = {
  children: ReactNode;
  fallback: ReactNode;
};

type GalaxyCanvasBoundaryState = {
  hasError: boolean;
};

// Isola falhas de renderização da galáxia 3D (contexto WebGL perdido,
// driver indisponível, etc.) para que o resto da página — cabeçalho, lista
// de experiências abaixo — nunca desapareça junto (ver GalaxyHub.tsx). Só
// existe porque Error Boundaries do React exigem um componente de classe;
// nenhuma outra lógica vive aqui.
export default class GalaxyCanvasBoundary extends Component<GalaxyCanvasBoundaryProps, GalaxyCanvasBoundaryState> {
  state: GalaxyCanvasBoundaryState = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: unknown) {
    console.error("Galáxia 3D falhou ao renderizar — usando o fallback em lista.", error);
  }

  render() {
    if (this.state.hasError) return this.props.fallback;
    return this.props.children;
  }
}
