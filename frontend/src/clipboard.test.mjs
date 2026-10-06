import { test } from 'node:test'
import assert from 'node:assert/strict'
import { copyText } from './clipboard.ts'

function browser({ writeText, commandResult = true } = {}) {
  const nodes = []
  const focused = { count: 0, focus() { this.count++ } }
  const body = { appendChild(node) { nodes.push(node) } }
  const document = {
    activeElement: focused, body,
    createElement() { return { style: {}, value: '', setAttribute() {}, focus() {}, select() {}, remove() { this.removed = true } } },
    execCommand() { return commandResult },
  }
  globalThis.document = document
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: { clipboard: writeText ? { writeText } : undefined } })
  return { nodes, focused }
}

test('uses clipboard API when available', async () => {
  let copied = ''
  const env = browser({ writeText: async value => { copied = value } })
  await copyText('hello')
  assert.equal(copied, 'hello')
  assert.equal(env.nodes.length, 0)
})

test('falls back to hidden textarea and cleans up/restores focus', async () => {
  const env = browser({ writeText: async () => { throw new Error('denied') } })
  await copyText('fallback')
  assert.equal(env.nodes.length, 1)
  assert.equal(env.nodes[0].value, 'fallback')
  assert.equal(env.nodes[0].removed, true)
  assert.equal(env.focused.count, 1)
})

test('throws if both clipboard paths fail and still cleans up', async () => {
  const env = browser({ writeText: async () => { throw new Error('denied') }, commandResult: false })
  await assert.rejects(copyText('failure'), /Copy command failed/)
  assert.equal(env.nodes[0].removed, true)
  assert.equal(env.focused.count, 1)
})
