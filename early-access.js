/* ==========================================================================
   Node AI — early-access signup module.

   joinnode.ai is static nginx with no backend, so the form posts cross-origin
   to the NodeAI app. That endpoint (/api/early-access) is deliberately public;
   its origin allowlist, honeypot and rate limit live server-side.

   Drives three shapes from one file:
     - the homepage module   (two modes behind a segmented control)
     - the /brands and /nodes modules (one audience, full field set)
     - the two /early-access landing pages
   Anything with [data-ea-form] is wired; anything with [data-ea-seg] switches
   between the forms inside the same [data-ea-root].
   ========================================================================== */
(function () {
  'use strict'

  var API = 'https://nodeai-published.kaymen.dev/api/early-access'

  var TICK =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6">' +
    '<path d="M20 6L9 17l-5-5"/></svg>'

  /* Attribution. Captured once per page load and stamped onto whichever form is
     submitted — without it the two LinkedIn landing pages are unmeasurable and
     "which of the six placements is working" has no answer. */
  function attribution() {
    var p
    try { p = new URLSearchParams(window.location.search) } catch (e) { p = null }
    var get = function (k) { return (p && p.get(k)) || null }
    return {
      utm_source: get('utm_source'),
      utm_medium: get('utm_medium'),
      utm_campaign: get('utm_campaign'),
      referrer: document.referrer || null,
      landing_path: window.location.pathname || null,
    }
  }

  function collect(form) {
    var payload = { audience: form.getAttribute('data-audience') }
    var fields = form.querySelectorAll('input[name], select[name], textarea[name]')
    for (var i = 0; i < fields.length; i++) {
      var el = fields[i]
      var v = (el.value || '').trim()
      if (v) payload[el.name] = v
    }
    var a = attribution()
    for (var k in a) if (a[k]) payload[k] = a[k]
    return payload
  }

  /* Mirrors the server's REQUIRED lists so a person is told what's missing
     before a round trip. The server re-checks — this is courtesy, not security. */
  var REQUIRED = {
    brand: { email: 'a work email', store_url: 'your store URL', monthly_orders: 'orders per month' },
    node: {
      email: 'an email', first_name: 'your name', phone: 'a phone number',
      neighborhood_or_zip: 'your neighborhood or ZIP',
    },
  }

  function missingFrom(payload) {
    var need = REQUIRED[payload.audience] || {}
    var out = []
    for (var k in need) if (!payload[k]) out.push(need[k])
    return out
  }

  function showError(form, message) {
    var box = form.querySelector('[data-ea-error]')
    if (!box) return
    box.textContent = message
    box.style.display = 'block'
  }

  function clearError(form) {
    var box = form.querySelector('[data-ea-error]')
    if (box) box.style.display = 'none'
  }

  function succeed(form) {
    var done = form.getAttribute('data-done-title') || 'You’re on the list.'
    var body =
      form.getAttribute('data-done-body') ||
      'We’ll be in touch as we open spots in your area.'
    var panel = document.createElement('div')
    panel.className = 'ea-done'
    panel.setAttribute('role', 'status')
    panel.innerHTML =
      '<div class="ea-tick">' + TICK + '</div>' +
      '<h4></h4><p></p>'
    panel.querySelector('h4').textContent = done
    panel.querySelector('p').textContent = body

    // Replace the form AND the segmented control: once someone has signed up,
    // offering them the other tab is just clutter.
    var root = form.closest('[data-ea-root]') || form.parentNode
    var seg = root.querySelector('[data-ea-seg]')
    if (seg) seg.style.display = 'none'
    var forms = root.querySelectorAll('[data-ea-form]')
    for (var i = 0; i < forms.length; i++) forms[i].style.display = 'none'
    form.parentNode.insertBefore(panel, form)
  }

  function submit(form) {
    var payload = collect(form)

    var missing = missingFrom(payload)
    if (missing.length) {
      showError(form, 'Please add ' + missing.join(', ') + '.')
      return
    }
    clearError(form)

    var button = form.querySelector('[data-ea-submit]')
    var label = button ? button.innerHTML : null
    if (button) { button.disabled = true; button.textContent = 'Sending…' }

    var restore = function () {
      if (button) { button.disabled = false; if (label !== null) button.innerHTML = label }
    }

    fetch(API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
      .then(function (res) {
        return res.json().catch(function () { return {} }).then(function (data) {
          return { ok: res.ok, data: data }
        })
      })
      .then(function (r) {
        if (!r.ok) {
          restore()
          showError(form, r.data.error || 'Something went wrong. Please try again.')
          return
        }
        succeed(form)
      })
      .catch(function () {
        restore()
        showError(
          form,
          'We could not reach the server. Check your connection, or email elor@joinnode.ai.'
        )
      })
  }

  function wireSegment(root) {
    var seg = root.querySelector('[data-ea-seg]')
    if (!seg) return
    var buttons = seg.querySelectorAll('button[data-mode]')
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].addEventListener('click', function (e) {
        var mode = e.currentTarget.getAttribute('data-mode')
        for (var j = 0; j < buttons.length; j++) {
          var on = buttons[j] === e.currentTarget
          buttons[j].classList.toggle('is-on', on)
          buttons[j].setAttribute('aria-selected', on ? 'true' : 'false')
        }
        var forms = root.querySelectorAll('[data-ea-form]')
        for (var k = 0; k < forms.length; k++) {
          forms[k].hidden = forms[k].getAttribute('data-audience') !== mode
        }
      })
    }
  }

  function init() {
    var roots = document.querySelectorAll('[data-ea-root]')
    for (var i = 0; i < roots.length; i++) wireSegment(roots[i])

    var forms = document.querySelectorAll('[data-ea-form]')
    for (var n = 0; n < forms.length; n++) {
      forms[n].addEventListener('submit', function (e) {
        e.preventDefault()
        submit(e.currentTarget)
      })
    }

    // The no-JS fallback is in the markup and visible by default, so that a
    // browser which never runs this file still shows a way to reach us.
    var fallbacks = document.querySelectorAll('[data-ea-nojs]')
    for (var f = 0; f < fallbacks.length; f++) fallbacks[f].style.display = 'none'
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init)
  } else {
    init()
  }
})()
