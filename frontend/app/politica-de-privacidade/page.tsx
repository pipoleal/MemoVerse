import type { Metadata } from "next";

import InstitutionalPage from "@/components/layout/InstitutionalPage";

export const metadata: Metadata = {
  title: "Política de Privacidade | MemoVerse",
  description: "Como o MemoVerse trata dados pessoais e conteúdos enviados à plataforma.",
};

export default function PrivacyPolicyPage() {
  return (
    <InstitutionalPage eyebrow="Institucional" title="Política de Privacidade" updatedAt="28 de agosto de 2026">
      <section>
        <h2 className="text-2xl font-bold text-white">1. Quem controla seus dados</h2>
        <p className="mt-4">
          O MemoVerse é operado por Felipe Santos de Sá Leal, responsável pelas decisões sobre o tratamento de dados
          pessoais realizado pela plataforma. Para assuntos de privacidade, entre em contato por{" "}
          <a className="text-yellow-300 underline underline-offset-4 hover:text-yellow-200" href="mailto:MemoryVersebr@gmail.com">
            MemoryVersebr@gmail.com
          </a>
          .
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white">2. Dados que podemos tratar</h2>
        <p className="mt-4">
          Podemos tratar dados de cadastro e acesso, como nome e e-mail; informações necessárias para criar e manter
          sua conta; o conteúdo que você insere nas experiências, como textos, fotos, vídeos, nomes e mensagens; e
          dados técnicos necessários para segurança e funcionamento da plataforma.
        </p>
        <p className="mt-4">
          Quando houver pagamento, o parceiro de pagamento processará os dados necessários para essa operação. O
          MemoVerse pode receber informações como status, identificadores e referências da transação.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white">3. Finalidades</h2>
        <p className="mt-4">
          Usamos esses dados para prestar o serviço, criar e exibir as experiências solicitadas, autenticar acessos,
          processar pagamentos quando aplicável, prevenir fraudes, responder solicitações e cumprir obrigações legais.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white">4. Compartilhamento e infraestrutura</h2>
        <p className="mt-4">
          Para operar a plataforma, podemos utilizar fornecedores de hospedagem, armazenamento de mídia, processamento
          de pagamentos e serviços de música vinculados por você. Esses fornecedores tratam dados apenas na medida
          necessária para oferecer seus respectivos serviços, conforme suas próprias políticas e contratos aplicáveis.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white">5. Armazenamento e segurança</h2>
        <p className="mt-4">
          Mantemos os dados pelo tempo necessário para prestar o serviço, atender solicitações e cumprir obrigações
          legais. Adotamos medidas técnicas e organizacionais razoáveis para proteger as informações, mas nenhum
          ambiente digital é totalmente livre de riscos.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white">6. Seus direitos</h2>
        <p className="mt-4">
          Nos termos da legislação aplicável, você pode solicitar confirmação de tratamento, acesso, correção,
          anonimização, bloqueio, eliminação, informação sobre compartilhamentos e revisão das suas escolhas de
          consentimento, quando aplicável. Para exercer seus direitos, use o e-mail de contato indicado nesta política.
        </p>
      </section>

      <section>
        <h2 className="text-2xl font-bold text-white">7. Atualizações desta política</h2>
        <p className="mt-4">
          Esta política pode ser atualizada para refletir mudanças no MemoVerse ou na legislação. A versão vigente
          estará sempre disponível nesta página, com sua data de atualização.
        </p>
      </section>
    </InstitutionalPage>
  );
}
