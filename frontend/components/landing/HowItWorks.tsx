import FadeIn from "../animations/FadeIn";

const STEPS = [
  {
    icon: "💌",
    title: "Escreva sua carta",
    desc: "Coloque em palavras o que essa memória significa para você. Escreva um momento, escolha uma data e veja um novo ponto de luz nascer no seu céu.",
  },
  {
    icon: "📸",
    title: "Adicione fotos e vídeos",
    desc: "Selecione fotos e vídeos marcantes que registram a sua memória. Reúna os momentos que contam a história — quantos quiser, na ordem que fizer sentido.",
  },
  {
    icon: "🎵",
    title: "Escolha música e tema",
    desc: "Uma trilha sonora e um dos temas visuais dão o clima certo à experiência.",
  },
  {
    icon: "🔗",
    title: "Compartilhe o link",
    desc: "Publique e envie — para guardar com você ou para presentear alguém especial.",
  },
];

export default function HowItWorks() {
  return (
    <section id="como-funciona" className="px-6 py-24 sm:py-32">
      <div className="mx-auto max-w-6xl">
        <FadeIn>
          <div className="mx-auto max-w-xl text-center">
            <p className="text-xs font-semibold uppercase tracking-[0.35em] text-yellow-400">Como funciona</p>
            <h2 className="mt-4 text-3xl font-black text-white sm:text-4xl">De uma lembrança a uma experiência</h2>
            <p className="mt-4 text-slate-400">Um passo a passo simples — sem precisar saber nada de tecnologia.</p>
          </div>
        </FadeIn>

        <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step, index) => (
            <FadeIn key={step.title} delay={index * 0.1}>
              <div className="flex h-full flex-col rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur-xl transition-all duration-300 hover:-translate-y-2 hover:border-white/20">
                <span className="text-4xl">{step.icon}</span>
                <p className="mt-5 text-[11px] font-bold uppercase tracking-[0.2em] text-slate-500">
                  Passo {index + 1}
                </p>
                <h3 className="mt-2 text-lg font-bold text-white">{step.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-400">{step.desc}</p>
              </div>
            </FadeIn>
          ))}
        </div>
      </div>
    </section>
  );
}
