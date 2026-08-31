import { cormorant } from "@/lib/fonts";
import FadeIn from "../animations/FadeIn";

export default function GiftCallout() {
  return (
    <section className="px-6 py-24 sm:py-32">
      <FadeIn>
        <div className="mx-auto max-w-3xl rounded-3xl border border-white/10 bg-linear-to-br from-yellow-400/10 via-white/5 to-transparent p-10 text-center sm:p-14">
          <span className="text-4xl">🎁</span>
          <h2 className={`${cormorant.className} mt-5 text-2xl italic text-white sm:text-3xl`}>
            Uma memória também é um presente
          </h2>
          <p className="mx-auto mt-4 max-w-xl text-slate-400">
            Crie a experiência e envie o link para quem você ama. Quem recebe pode reviver a memória — e guardar essa
            experiência na própria galáxia, se quiser.
          </p>
        </div>
      </FadeIn>
    </section>
  );
}
