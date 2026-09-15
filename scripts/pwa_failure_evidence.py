"""Bounded, read-only browser observations for the PWA fixture."""
from __future__ import annotations
import time

INIT_SCRIPT = r"""(() => {
  const events = [];
  const record = (kind, detail = {}) => {
    if (events.length >= 500) return;
    const event = {kind, timestamp: Date.now(), ...detail};
    events.push(event);
    globalThis.__recordPwaFailureEvent?.(event).catch(() => {});
  };
  const seen = new WeakSet();
  const worker = (value, role) => {
    if (!value) return null;
    if (!seen.has(value)) {
      seen.add(value);
      value.addEventListener('statechange', () => record('statechange', {role, state:value.state, url:value.scriptURL}));
    }
    return {state:value.state, url:value.scriptURL};
  };
  const snapshot = registration => ({
    scope:registration.scope, active:worker(registration.active, 'active'),
    waiting:worker(registration.waiting, 'waiting'), installing:worker(registration.installing, 'installing')
  });
  const registrations = new WeakSet();
  const observe = registration => {
    if (!registrations.has(registration)) {
      registrations.add(registration);
      record('registration', snapshot(registration));
      registration.addEventListener('updatefound', () => record('updatefound', snapshot(registration)));
    }
    return registration;
  };
  if ('serviceWorker' in navigator) {
    const original = navigator.serviceWorker.register.bind(navigator.serviceWorker);
    navigator.serviceWorker.register = (...args) => original(...args).then(observe);
    navigator.serviceWorker.addEventListener('controllerchange', () => record('controllerchange', {controller:worker(navigator.serviceWorker.controller, 'controller')}));
    navigator.serviceWorker.addEventListener('message', event => {
      if (event.data?.type === '__pwa_fixture_worker_version__') record('observed-worker-version', {version:event.data.version});
    });
    navigator.serviceWorker.getRegistrations().then(values => values.forEach(observe));
  }
  globalThis.__pwaFailureEvidence = async () => ({events, controller:worker(navigator.serviceWorker?.controller, 'controller'),
    registrations: 'serviceWorker' in navigator ? (await navigator.serviceWorker.getRegistrations()).map(snapshot) : []});
})();"""


def attach(context, evidence):
    evidence['lifecycle'] = []
    evidence['network'] = []
    evidence['page_errors'] = []
    evidence['console'] = []
    def record(key, value):
        if len(evidence[key]) < 500:
            evidence[key].append({'monotonic_seconds': time.monotonic(), **value})
    context.expose_binding('__recordPwaFailureEvent',
                           lambda source, event: record('lifecycle', {'url': source['page'].url, **event}))
    context.add_init_script(INIT_SCRIPT)
    context.on('request', lambda r: record('network', {'event':'request','url':r.url,'method':r.method}))
    context.on('response', lambda r: record('network', {'event':'response','url':r.url,'status':r.status}))
    context.on('requestfailed', lambda r: record('network', {'event':'requestfailed','url':r.url,'failure':r.failure}))
    def page_created(page):
        page.on('pageerror', lambda error: record('page_errors', {'error':str(error)}))
        page.on('console', lambda msg: record('console', {'type':msg.type,'text':msg.text[:2000]}) if msg.type in ('warning','error') else None)
    context.on('page', page_created)


def snapshot(context, evidence):
    evidence['pages'] = []
    for page in context.pages:
        if page.is_closed():
            continue
        try:
            evidence['pages'].append({'url':page.url, **page.evaluate('async () => await globalThis.__pwaFailureEvidence?.() || {}')})
        except Exception as exc:
            evidence['pages'].append({'url':page.url,'snapshot_error':str(exc)})
