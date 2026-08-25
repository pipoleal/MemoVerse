// Rodapé institucional reutilizável — usado em Landing, Login, Cadastro e
// (via DashboardShell) Dashboard/Minha Galáxia. Nenhum estado/interação
// própria (só links reais), por isso não precisa de "use client".
//
// "Sobre", "Termos de Uso" e "Política de Privacidade" ainda não têm rota
// real no app (nenhuma dessas páginas existe hoje) — ficam como texto
// preparado, não como link, para nunca apontar para uma página inexistente.
// Trocar por <Link> assim que as rotas existirem.
// Número oficial: (55) 12 99243-2849 — wa.me exige só dígitos (país + DDD +
// número), por isso não há uma constante de exibição separada: o número
// nunca aparece como texto no rodapé agora, só o ícone (ver aria-label).
const WHATSAPP_URL = "https://wa.me/5512992432849";
const EMAIL_ADDRESS = "MemoryVersebr@gmail.com";
// Perfil oficial @memoversebr.
const INSTAGRAM_URL = "https://www.instagram.com/memoversebr/";

type FooterProps = {
  // "full": rodapé institucional completo (Landing/Login/Cadastro/Dashboard).
  // "compact": só a linha de crédito, para áreas onde um rodapé grande
  // atrapalharia a imersão (ex. o desfecho da experiência pública).
  variant?: "full" | "compact";
  className?: string;
};

// Ícones desenhados à mão em SVG (sem biblioteca — nenhuma está instalada
// no projeto hoje, ver package.json) — herdam a cor via currentColor, então
// o próprio <a> controla cor padrão/hover/transição, nunca o ícone.
function WhatsAppIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5" aria-hidden="true">
      <path d="M12.001 2C6.478 2 2 6.477 2 12c0 1.887.525 3.647 1.438 5.152L2 22l4.955-1.412A9.94 9.94 0 0 0 12.001 22C17.524 22 22 17.523 22 12S17.524 2 12.001 2Zm5.451 14.146c-.229.646-1.34 1.234-1.85 1.31-.472.07-1.06.1-1.71-.107-.394-.126-.9-.293-1.549-.573-2.724-1.176-4.5-3.918-4.636-4.1-.135-.183-1.11-1.475-1.11-2.815 0-1.34.703-1.998.953-2.271.25-.273.545-.34.727-.34.182 0 .364.002.523.01.168.008.393-.064.615.469.229.55.777 1.898.847 2.036.07.14.117.303.024.487-.093.183-.14.297-.28.457-.14.16-.294.357-.42.48-.14.14-.286.29-.123.57.163.28.727 1.2 1.56 1.945 1.073.958 1.977 1.255 2.257 1.396.28.14.443.117.606-.07.163-.187.7-.816.887-1.096.187-.28.373-.233.63-.14.257.093 1.634.77 1.914.91.28.14.467.21.537.327.07.117.07.677-.16 1.323Z" />
    </svg>
  );
}

function MailIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5" aria-hidden="true">
      <path d="M1.5 8.67v8.58a3 3 0 0 0 3 3h15a3 3 0 0 0 3-3V8.67l-8.928 5.493a3 3 0 0 1-3.144 0L1.5 8.67Z" />
      <path d="M22.5 6.908V6.75a3 3 0 0 0-3-3h-15a3 3 0 0 0-3 3v.158l9.714 5.978a1.5 1.5 0 0 0 1.572 0L22.5 6.908Z" />
    </svg>
  );
}

function InstagramIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5" aria-hidden="true">
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M12 2c-2.717 0-3.056.012-4.123.06-1.065.049-1.79.218-2.427.465a4.902 4.902 0 0 0-1.772 1.153A4.902 4.902 0 0 0 2.525 5.45c-.247.637-.416 1.362-.465 2.427C2.012 8.944 2 9.283 2 12s.012 3.056.06 4.123c.049 1.065.218 1.79.465 2.427a4.902 4.902 0 0 0 1.153 1.772 4.902 4.902 0 0 0 1.772 1.153c.637.247 1.362.416 2.427.465C8.944 21.988 9.283 22 12 22s3.056-.012 4.123-.06c1.065-.049 1.79-.218 2.427-.465a4.902 4.902 0 0 0 1.772-1.153 4.902 4.902 0 0 0 1.153-1.772c.247-.637.416-1.362.465-2.427.048-1.067.06-1.406.06-4.123s-.012-3.056-.06-4.123c-.049-1.065-.218-1.79-.465-2.427a4.902 4.902 0 0 0-1.153-1.772A4.902 4.902 0 0 0 18.55 2.525c-.637-.247-1.362-.416-2.427-.465C15.056 2.012 14.717 2 12 2Zm0 1.802c2.67 0 2.987.01 4.042.059.976.045 1.505.207 1.858.344.467.182.8.399 1.15.748.35.35.566.683.748 1.15.137.353.3.882.344 1.858.048 1.054.058 1.37.058 4.041 0 2.67-.01 2.987-.058 4.041-.044.976-.207 1.505-.344 1.858a3.098 3.098 0 0 1-.748 1.15 3.098 3.098 0 0 1-1.15.748c-.353.137-.882.3-1.858.344-1.054.048-1.37.058-4.042.058-2.67 0-2.987-.01-4.04-.058-.977-.044-1.505-.207-1.858-.344a3.098 3.098 0 0 1-1.15-.748 3.098 3.098 0 0 1-.749-1.15c-.137-.353-.3-.882-.344-1.858-.048-1.054-.058-1.37-.058-4.041 0-2.67.01-2.987.058-4.041.045-.976.207-1.505.344-1.858.182-.467.399-.8.749-1.15.35-.35.683-.566 1.15-.748.353-.137.882-.3 1.858-.344 1.054-.048 1.37-.059 4.04-.059Z"
      />
      <path d="M12 6.865a5.135 5.135 0 1 0 0 10.27 5.135 5.135 0 0 0 0-10.27Zm0 8.468a3.333 3.333 0 1 1 0-6.666 3.333 3.333 0 0 1 0 6.666ZM17.338 6.662a1.2 1.2 0 1 1-2.4 0 1.2 1.2 0 0 1 2.4 0Z" />
    </svg>
  );
}

// Área de toque confortável (44px) sem deixar o ícone (20px) visualmente
// grande — o padding extra é invisível, só aumenta o alvo de clique/toque.
const CONTACT_ICON_LINK_CLASS =
  "inline-flex h-11 w-11 cursor-pointer items-center justify-center rounded-full text-slate-300 transition-colors duration-300 hover:text-yellow-400";

export default function Footer({ variant = "full", className = "" }: FooterProps) {
  if (variant === "compact") {
    return (
      <footer className={`border-t border-white/10 px-6 py-6 text-center text-xs text-slate-400 ${className}`}>
        <p>
          Feito com <span className="text-yellow-400">♥</span> no MemoVerse
        </p>
        <p className="mt-1">Desenvolvido por Felipe Leal.</p>
      </footer>
    );
  }

  return (
    <footer className={`border-t border-white/10 bg-slate-950/80 px-6 py-14 backdrop-blur-xl sm:px-8 ${className}`}>
      <div className="mx-auto grid max-w-6xl gap-10 sm:grid-cols-2 md:grid-cols-3">
        <div>
          <span className="bg-linear-to-r from-white via-slate-200 to-yellow-300 bg-clip-text text-xl font-black text-transparent">
            MemoVerse
          </span>
          <p className="mt-3 max-w-xs text-sm text-slate-400">Transformando momentos em memórias que ficam.</p>
        </div>

        <div>
          <h3 className="text-xs font-semibold uppercase tracking-[0.2em] text-yellow-400">Contato</h3>
          {/* Só ícones, sem rótulo ao lado — texto equivalente vive em
              aria-label/title para leitor de tela e tooltip. Centralizado
              no mobile (coluna única do grid); alinhado à esquerda, sob o
              título, a partir de sm. */}
          <div className="mt-4 flex items-center justify-center gap-5 sm:justify-start">
            <a
              href={WHATSAPP_URL}
              target="_blank"
              rel="noopener noreferrer"
              aria-label="WhatsApp"
              title="WhatsApp"
              className={CONTACT_ICON_LINK_CLASS}
            >
              <WhatsAppIcon />
            </a>
            <a href={`mailto:${EMAIL_ADDRESS}`} aria-label="E-mail" title="E-mail" className={CONTACT_ICON_LINK_CLASS}>
              <MailIcon />
            </a>
            <a
              href={INSTAGRAM_URL}
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Instagram"
              title="Instagram"
              className={CONTACT_ICON_LINK_CLASS}
            >
              <InstagramIcon />
            </a>
          </div>
        </div>

        <div>
          <h3 className="text-xs font-semibold uppercase tracking-[0.2em] text-yellow-400">Institucional</h3>
          <ul className="mt-4 space-y-2 text-sm text-slate-500">
            <li title="Em breve">Sobre</li>
            <li title="Em breve">Termos de Uso</li>
            <li title="Em breve">Política de Privacidade</li>
          </ul>
        </div>
      </div>

      <div className="mx-auto mt-12 max-w-6xl border-t border-white/10 pt-6 text-xs text-slate-500">
        <p>© 2026 MemoVerse. Todos os direitos reservados.</p>
        <p className="mt-1">Desenvolvido por Felipe Leal.</p>
      </div>
    </footer>
  );
}
