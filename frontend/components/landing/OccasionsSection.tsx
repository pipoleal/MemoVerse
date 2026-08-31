import { cormorant } from "@/lib/fonts";
import FadeIn from "../animations/FadeIn";

// Mesmas categorias de "Etapa 1" do wizard (TypeStep — Pedido de Namoro,
// Pedido de Casamento, Aniversário...) — aqui só como selo ilustrativo,
// nunca um seletor funcional: não navega nem filtra nada, só reforça que
// o MemoVerse não é só para memorial.
const OCCASIONS = ["Namoro", "Amizade", "Casamento", "Homenagem", "Aniversário", "Mêsversário", "Personalizado"];

export default function OccasionsSection() {
  return (
    <section className="px-6 py-24 text-center sm:py-32">
      <FadeIn>
        <p className="text-xs font-semibold uppercase tracking-[0.35em] text-yellow-400">
          Pra qualquer momento que importa
        </p>
        <h2 className={`${cormorant.className} mx-auto mt-4 max-w-3xl text-3xl uppercase leading-tight text-white sm:text-5xl`}>
          Feito para mais de uma ocasião.
        </h2>
        <p className="mx-auto mt-5 max-w-xl text-slate-400">
          Memorial é só um dos usos — o MemoVerse acompanha qualquer data que mereça ser lembrada.
        </p>

        <div className="mx-auto mt-10 flex max-w-2xl flex-wrap justify-center gap-4">
          {OCCASIONS.map((occasion) => (
            <span
              key={occasion}
              className="rounded-full border border-yellow-400/40 px-6 py-3 text-sm font-semibold text-yellow-300"
            >
              {occasion}
            </span>
          ))}
        </div>
      </FadeIn>
    </section>
  );
}
