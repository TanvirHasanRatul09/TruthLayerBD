import assert from 'node:assert/strict'
import { readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { test } from 'node:test'
import vm from 'node:vm'

const root = new URL('../', import.meta.url).pathname.replace(/^\/(?=[A-Za-z]:)/, '')
const manifest = JSON.parse(readFileSync(join(root, 'dist/manifest.webmanifest'), 'utf8'))

test('production manifest has installable icons and standalone launch', () => {
  assert.equal(manifest.display, 'standalone')
  assert.equal(manifest.start_url, '/#/')
  for (const size of [192, 512]) {
    const icon = manifest.icons.find(item => item.sizes === `${size}x${size}`)
    assert.ok(icon)
    assert.ok(statSync(join(root, 'dist', icon.src)).size > 100)
  }
})

test('service worker serves cached app shell for offline navigation and never handles API requests', async () => {
  const listeners = new Map()
  const cached = new Map([['/', { status: 200, shell: true }], ['/offline.html', { status: 200, offline: true }]])
  const context = {
    URL,
    Response,
    self: {
      location: { origin: 'https://truthlayer.example' },
      clients: { claim: async () => {} },
      addEventListener: (name, handler) => listeners.set(name, handler),
    },
    caches: {
      match: async key => cached.get(key),
      open: async () => ({ addAll: async () => {}, put: async (key, value) => cached.set(key, value) }),
      keys: async () => [],
      delete: async () => {},
    },
    fetch: async () => { throw Error('offline') },
  }
  vm.runInNewContext(readFileSync(join(root, 'dist/sw.js'), 'utf8'), context)
  let response
  listeners.get('fetch')({
    request: { method: 'GET', mode: 'navigate', url: 'https://truthlayer.example/#/history' },
    respondWith: promise => { response = promise },
  })
  assert.equal((await response).shell, true)
  let intercepted = false
  listeners.get('fetch')({
    request: { method: 'GET', mode: 'cors', url: 'https://truthlayer.example/api/v1/analyses' },
    respondWith: () => { intercepted = true },
  })
  assert.equal(intercepted, false)
})
