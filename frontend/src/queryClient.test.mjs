import test from 'node:test'
import assert from 'node:assert/strict'
import { createAppQueryClient, clearPrivateQueries, accessKey, authKey } from './queryClient.ts'
import { ApiError, NetworkError } from './api/client.ts'

test('query and mutation failures close the gate without treating LLM errors as disconnects', async () => {
  const client = createAppQueryClient()
  for (const [error, kind] of [[new ApiError('Erişim anahtarı gerekli.', 401), 'unauthorized'], [new ApiError('API_TOKEN ayarlanmalı.', 403), 'forbidden'], [new NetworkError(), 'offline']]) {
    await assert.rejects(client.fetchQuery({ queryKey: ['probe', kind], queryFn: async () => { throw error } }))
    assert.equal(client.getQueryData(accessKey).kind, kind)
  }
  client.setQueryData(accessKey, null)
  const llm = client.getMutationCache().build(client, { mutationFn: async () => { throw new ApiError('CLI kurulu değil.', 503) } })
  await assert.rejects(llm.execute())
  assert.equal(client.getQueryData(accessKey), null)
  const expired = client.getMutationCache().build(client, { mutationFn: async () => { throw new ApiError('Erişim anahtarı gerekli.', 401) } })
  await assert.rejects(expired.execute())
  assert.equal(client.getQueryData(accessKey).kind, 'unauthorized')
  assert.equal(client.getQueryData(authKey).authenticated, false)
  client.clear()
})

test('session changes discard private cached data and mutation results', async () => {
  const client = createAppQueryClient()
  client.setQueryData(authKey, { token_required: true, authenticated: false })
  client.setQueryData(['profile'], { full_name: 'Demo' })
  await clearPrivateQueries(client)
  assert.equal(client.getQueryData(['profile']), undefined)
  assert.equal(client.getQueryData(authKey).authenticated, false)
  client.clear()
})
