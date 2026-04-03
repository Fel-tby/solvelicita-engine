import { useRouter } from 'next/router'
import SiteLayout from '../components/SiteLayout'

export default function ContatoPage() {
  const router = useRouter()
  const enviado = router.query.sent === '1'
  const erro = router.query.error === '1'

  return (
    <SiteLayout
      title="SolveLicita - Contato"
      description="Entre em contato com o projeto."
      activeNav="contato"
    >
      <section id="contato" className="section active">
        <div className="contato-wrap">
          <h1>Contato</h1>
          <p>
            Tem feedback, encontrou algo errado, quer colaborar, ou so quer
            entender melhor o projeto? Mande sua mensagem por aqui.
          </p>

          <form
            action="/api/contact"
            method="POST"
            className="contato-form"
          >
            <input type="text" name="_honey" style={{ display: 'none' }} tabIndex="-1" autoComplete="off" />

            <div className="form-row">
              <label className="form-label" htmlFor="contato-nome">Nome</label>
              <input
                id="contato-nome"
                name="nome"
                type="text"
                className="form-input"
                placeholder="Seu nome"
                required
              />
            </div>

            <div className="form-row">
              <label className="form-label" htmlFor="contato-email">E-mail</label>
              <input
                id="contato-email"
                name="email"
                type="email"
                className="form-input"
                placeholder="email@exemplo.com"
                required
              />
            </div>

            <div className="form-row">
              <label className="form-label" htmlFor="contato-assunto">Assunto</label>
              <select
                id="contato-assunto"
                name="assunto"
                className="form-select"
                defaultValue=""
                required
              >
                <option value="" disabled>Selecione...</option>
                <option value="Feedback tecnico">Feedback tecnico</option>
                <option value="Erro nos dados">Erro nos dados</option>
                <option value="Quero colaborar">Quero colaborar</option>
                <option value="Imprensa">Imprensa</option>
                <option value="Outro">Outro</option>
              </select>
            </div>

            <div className="form-row">
              <label className="form-label" htmlFor="contato-mensagem">Mensagem</label>
              <textarea
                id="contato-mensagem"
                name="mensagem"
                className="form-textarea"
                placeholder="Sua mensagem..."
                required
              />
            </div>

            <button className="form-submit" type="submit">
              Enviar mensagem
            </button>
          </form>

          {enviado ? (
            <p
              style={{
                marginTop: '12px',
                fontSize: '0.78rem',
                color: 'var(--green)',
                lineHeight: 1.6,
              }}
            >
              Mensagem enviada com sucesso.
            </p>
          ) : null}

          {erro ? (
            <p
              style={{
                marginTop: '12px',
                fontSize: '0.78rem',
                color: 'var(--red)',
                lineHeight: 1.6,
              }}
            >
              Nao foi possivel enviar a mensagem agora. Tente novamente em instantes.
            </p>
          ) : null}

          <div className="contato-alts">
            <div
              className="contato-alt"
              style={{ marginLeft: 'auto', marginRight: 'auto', textAlign: 'center' }}
            >
              <div className="contato-alt-label">GitHub</div>
              <a href="https://github.com/Fel-tby/solvelicita">github.com/Fel-tby/solvelicita</a>
            </div>
          </div>
        </div>
      </section>
    </SiteLayout>
  )
}
