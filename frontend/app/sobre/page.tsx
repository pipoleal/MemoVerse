import type { Metadata } from "next";

import InstitutionalPage from "@/components/layout/InstitutionalPage";

export const metadata: Metadata = {
  title: "Sobre o MemoVerse",
  description: "Conheça o MemoVerse e a ideia por trás de transformar momentos em memórias que ficam.",
};

export default function AboutPage() {
  return (
    <InstitutionalPage eyebrow="Institucional" title="Sobre o MemoVerse">
      <section>
        <h2 className="text-2xl font-bold text-white">Memórias merecem mais do que uma pasta no celular.</h2>
        <p className="mt-4">
          O MemoVerse nasceu para transformar fotos, palavras e músicas em experiências digitais que podem ser
          revisitadas e compartilhadas com quem importa.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white">Como funciona</h2>
        <p className="mt-4">
          Você cria uma experiência, reúne a sua história em texto, fotos, vídeos e música e recebe uma página para
          guardar ou presentear. Cada memória é construída para ter significado, não apenas para ocupar espaço.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white">Nosso compromisso</h2>
        <p className="mt-4">
          Tratamos cada experiência como algo pessoal. Por isso, buscamos construir um produto simples, sensível e
          transparente sobre como as informações são usadas e protegidas.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white">Contato</h2>
        <p className="mt-4">
          O MemoVerse é operado por Felipe Santos de Sá Leal. Para falar conosco, escreva para{" "}
          <a className="text-yellow-300 underline underline-offset-4 hover:text-yellow-200" href="mailto:MemoryVersebr@gmail.com">
            MemoryVersebr@gmail.com
          </a>
          .
        </p>
      </section>
    </InstitutionalPage>
  );
}
