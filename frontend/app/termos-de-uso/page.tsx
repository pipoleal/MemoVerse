import type { Metadata } from "next";

import InstitutionalPage from "@/components/layout/InstitutionalPage";

export const metadata: Metadata = {
  title: "Termos de Uso | MemoVerse",
  description: "Termos de uso da plataforma MemoVerse.",
};

export default function TermsOfUsePage() {
  return (
    <InstitutionalPage eyebrow="Institucional" title="Termos de Uso" updatedAt="28 de agosto de 2026">
      <section>
        <h2 className="text-2xl font-bold text-white">1. Aceitação</h2>
        <p className="mt-4">
          Ao acessar ou usar o MemoVerse, você concorda com estes Termos de Uso e com a nossa Política de
          Privacidade. Se não concordar, não utilize a plataforma.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white">2. O serviço</h2>
        <p className="mt-4">
          O MemoVerse permite criar experiências digitais com textos, fotos, vídeos, músicas e outros conteúdos
          fornecidos por você. Alguns recursos podem depender de pagamento e de serviços de terceiros.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white">3. Sua conta e seu conteúdo</h2>
        <p className="mt-4">
          Você é responsável pelas informações da sua conta e pelo conteúdo que envia. Ao publicar uma experiência,
          você declara que possui os direitos necessários sobre os textos, imagens, vídeos, músicas e dados pessoais
          incluídos nela, inclusive autorização das pessoas retratadas quando aplicável.
        </p>
        <p className="mt-4">
          Não envie conteúdo ilegal, ofensivo, que viole direitos de terceiros ou que exponha dados pessoais sem uma
          base legítima para isso.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white">4. Pagamentos</h2>
        <p className="mt-4">
          Pagamentos, quando disponíveis, são processados por parceiros especializados. O MemoVerse não solicita que
          você envie dados de cartão por e-mail ou mensagens. Condições, aprovação e eventuais recusas seguem também
          as regras do meio de pagamento utilizado.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white">5. Disponibilidade e alterações</h2>
        <p className="mt-4">
          Podemos atualizar, manter ou evoluir a plataforma para melhorar sua segurança e funcionamento. Faremos
          esforços razoáveis para manter o serviço disponível, mas não garantimos operação ininterrupta ou livre de
          falhas.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white">6. Privacidade e contato</h2>
        <p className="mt-4">
          O tratamento de dados pessoais é explicado na Política de Privacidade. Dúvidas sobre estes Termos podem ser
          enviadas para{" "}
          <a className="text-yellow-300 underline underline-offset-4 hover:text-yellow-200" href="mailto:MemoryVersebr@gmail.com">
            MemoryVersebr@gmail.com
          </a>
          .
        </p>
      </section>
    </InstitutionalPage>
  );
}
