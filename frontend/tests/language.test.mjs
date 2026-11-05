import assert from 'node:assert/strict'
import { test } from 'node:test'
import Module from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { build } from 'esbuild'
import React from 'react'
import { renderToStaticMarkup } from 'react-dom/server'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
async function components() {
  const result = await build({ stdin: { contents: "export { LanguageProvider } from './src/i18n.tsx'; export { default as HomePage } from './src/pages/HomePage.tsx'", resolveDir: root, sourcefile: 'language-entry.tsx' }, bundle: true, platform: 'node', format: 'cjs', packages: 'external', write: false, jsx: 'automatic', define: { 'import.meta.env.VITE_API_BASE_URL': JSON.stringify('/api/v1'), 'import.meta.env.PROD': 'false' } })
  const module = new Module(path.join(root, 'tests', 'language-compiled.cjs'))
  module.filename = path.join(root, 'tests', 'language-compiled.cjs')
  module.paths = Module._nodeModulePaths(path.join(root, 'tests'))
  module._compile(result.outputFiles[0].text, module.filename)
  return module.exports
}
const storage = new Map()
globalThis.localStorage = { getItem: key => storage.get(key) || null, setItem: (key, value) => storage.set(key, value) }
globalThis.window = { location: { hash: '#/' } }
Object.defineProperty(globalThis, 'navigator', { configurable: true, value: { onLine: true } })

test('default Bangla and saved English render the official sticker and translated welcome', async () => {
  const { LanguageProvider, HomePage } = await components()
  const render = () => renderToStaticMarkup(React.createElement(LanguageProvider, null, React.createElement(HomePage)))
  let html = render()
  assert.match(html, /ছবি আপলোড করুন/)
  assert.match(html, /official-buildathon-sticker\.png/)
  assert.match(html, /aria-pressed="true">বাংলা/)
  storage.set('truthlayer-language', 'en')
  html = render()
  assert.match(html, /Upload an image/)
  assert.match(html, /See the evidence behind its claim/)
  assert.match(html, /aria-pressed="true">English/)
  assert.match(html, /official-buildathon-sticker\.png/)
})
