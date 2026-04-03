const CONTACT_ENDPOINT_BASE = 'https://formsubmit.co/'

function normalizeField(value) {
  return Array.isArray(value) ? String(value[0] || '').trim() : String(value || '').trim()
}

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST')
    return res.status(405).send('Method Not Allowed')
  }

  const contactEmail = process.env.CONTACT_FORM_EMAIL
  if (!contactEmail) {
    return res.redirect(303, '/contato?error=1')
  }

  const nome = normalizeField(req.body?.nome)
  const email = normalizeField(req.body?.email)
  const assunto = normalizeField(req.body?.assunto)
  const mensagem = normalizeField(req.body?.mensagem)
  const honey = normalizeField(req.body?._honey)

  if (honey) {
    return res.redirect(303, '/contato?sent=1')
  }

  if (!nome || !email || !assunto || !mensagem) {
    return res.redirect(303, '/contato?error=1')
  }

  const payload = new URLSearchParams({
    nome,
    email,
    assunto,
    mensagem,
    _subject: 'Novo contato - SolveLicita',
    _template: 'table',
    _captcha: 'false',
  })

  try {
    const response = await fetch(`${CONTACT_ENDPOINT_BASE}${encodeURIComponent(contactEmail)}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        Accept: 'application/json',
      },
      body: payload.toString(),
    })

    if (!response.ok) {
      return res.redirect(303, '/contato?error=1')
    }

    return res.redirect(303, '/contato?sent=1')
  } catch (error) {
    return res.redirect(303, '/contato?error=1')
  }
}
