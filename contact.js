/* ==========================================================================
   Node AI — email contact panel.

   Every CTA that reaches a person (Talk to Elor, Get a demo, Become a node,
   Investors) is a mailto: link. On a laptop a mailto: link does nothing at all
   unless a desktop mail app is registered for it, which is not the case for
   anyone who reads mail in Gmail or Outlook in the browser — the click is
   silently swallowed (reported on /investor-deck, 2026-09-23).

   So on a mouse-driven device any mailto: click opens this panel instead: the
   address with a Copy button, and the same draft (subject and all) opened in
   Gmail, Outlook or the mail app. Phones keep the plain link — they always
   have a mail app and the panel would only add a tap. Without JavaScript, or
   without <dialog>, every link stays an ordinary mailto:.
   ========================================================================== */
(function () {
  'use strict'

  var desktop = window.matchMedia && window.matchMedia('(hover: hover) and (pointer: fine)')
  if (!desktop || typeof HTMLDialogElement !== 'function') return

  var ICON = {
    close: '<path d="M18 6 6 18M6 6l12 12"/>',
    copy: '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>',
    tick: '<path d="M20 6 9 17l-5-5"/>',
    out: '<path d="M7 17 17 7M8 7h9v9"/>',
    mail: '<rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 7-10 6L2 7"/>',
  }
  function svg(name) {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
      'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + ICON[name] + '</svg>'
  }

  var enc = encodeURIComponent

  /* mailto:addr?subject=…&body=… → its parts. */
  function parse(href) {
    var rest = href.replace(/^mailto:/i, '')
    var q = rest.indexOf('?')
    var params = new URLSearchParams(q < 0 ? '' : rest.slice(q + 1))
    var to = q < 0 ? rest : rest.slice(0, q)
    try { to = decodeURIComponent(to) } catch (e) { /* keep it raw */ }
    return { to: to, subject: params.get('subject') || '', body: params.get('body') || '', href: href }
  }

  function gmail(m) {
    return 'https://mail.google.com/mail/?view=cm&fs=1&to=' + enc(m.to) +
      (m.subject ? '&su=' + enc(m.subject) : '') + (m.body ? '&body=' + enc(m.body) : '')
  }
  function outlook(m) {
    return 'https://outlook.office.com/mail/deeplink/compose?to=' + enc(m.to) +
      (m.subject ? '&subject=' + enc(m.subject) : '') + (m.body ? '&body=' + enc(m.body) : '')
  }

  var dlg, el = {}, resetTimer

  function build() {
    dlg = document.createElement('dialog')
    dlg.className = 'ct'
    dlg.setAttribute('aria-labelledby', 'ct-addr')
    dlg.innerHTML =
      '<div class="ct-in">' +
        '<button type="button" class="ct-close" aria-label="Close">' + svg('close') + '</button>' +
        '<p class="ct-kick">Get in touch</p>' +
        '<div class="ct-row">' +
          '<p class="ct-addr" id="ct-addr"></p>' +
          '<button type="button" class="ct-copy"></button>' +
        '</div>' +
        '<p class="ct-subj">Subject: <b></b></p>' +
        '<p class="ct-label">Or open a draft in</p>' +
        '<div class="ct-opts">' +
          '<a class="ct-opt" data-ct="gmail" target="_blank" rel="noopener">Gmail' + svg('out') + '</a>' +
          '<a class="ct-opt" data-ct="outlook" target="_blank" rel="noopener">Outlook' + svg('out') + '</a>' +
          '<a class="ct-opt" data-ct="app">' + svg('mail') + 'Mail app</a>' +
        '</div>' +
      '</div>'
    document.body.appendChild(dlg)

    el.addr = dlg.querySelector('.ct-addr')
    el.copy = dlg.querySelector('.ct-copy')
    el.subj = dlg.querySelector('.ct-subj')
    el.gmail = dlg.querySelector('[data-ct="gmail"]')
    el.outlook = dlg.querySelector('[data-ct="outlook"]')
    el.app = dlg.querySelector('[data-ct="app"]')

    dlg.querySelector('.ct-close').addEventListener('click', function () { dlg.close() })
    /* .ct-in carries all the padding, so a click that lands on the dialog
       element itself can only be the backdrop. */
    dlg.addEventListener('click', function (e) { if (e.target === dlg) dlg.close() })
    /* The draft opens in a new tab; don't leave the panel over the page. */
    el.gmail.addEventListener('click', function () { dlg.close() })
    el.outlook.addEventListener('click', function () { dlg.close() })
    el.copy.addEventListener('click', copy)
  }

  function setCopy(state) {
    clearTimeout(resetTimer)
    el.copy.classList.toggle('done', state === 'done')
    if (state === 'done') {
      el.copy.innerHTML = svg('tick') + 'Copied'
      resetTimer = setTimeout(function () { setCopy('idle') }, 2200)
    } else if (state === 'manual') {
      el.copy.innerHTML = /Mac|iPhone|iPad/.test(navigator.platform) ? 'Press ⌘C' : 'Press Ctrl+C'
    } else {
      el.copy.innerHTML = svg('copy') + 'Copy'
    }
  }

  function copy() {
    var text = el.addr.textContent
    var done = function () { setCopy('done') }
    /* No clipboard API (or it refused): select the address so the keyboard
       shortcut the button now names does the job. */
    var manual = function () {
      var r = document.createRange()
      r.selectNodeContents(el.addr)
      var s = window.getSelection()
      s.removeAllRanges()
      s.addRange(r)
      setCopy('manual')
    }
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(done, manual)
    else manual()
  }

  function open(m) {
    if (!dlg) build()
    el.addr.textContent = m.to
    el.subj.hidden = !m.subject
    el.subj.querySelector('b').textContent = m.subject
    el.gmail.href = gmail(m)
    el.outlook.href = outlook(m)
    el.app.href = m.href
    setCopy('idle')
    dlg.showModal()
    el.copy.focus()
  }

  document.addEventListener('click', function (e) {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return
    var a = e.target.closest && e.target.closest('a[href^="mailto:"]')
    if (!a || a.closest('.ct') || !desktop.matches) return
    e.preventDefault()
    open(parse(a.href))
  })
})()
