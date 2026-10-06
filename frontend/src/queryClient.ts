import { MutationCache, QueryCache, QueryClient } from '@tanstack/react-query'
import { ApiError, NetworkError } from './api/client.ts'

export type AccessFailure = { kind: 'offline' | 'unauthorized' | 'forbidden'; message: string } | null
export const authKey = ['auth'] as const
export const accessKey = ['access-failure'] as const

export function createAppQueryClient() {
  const onError = (error: Error) => {
    let failure: AccessFailure = null
    if (error instanceof NetworkError) failure = { kind: 'offline', message: error.message }
    else if (error instanceof ApiError && error.status === 401) failure = { kind: 'unauthorized', message: error.message }
    else if (error instanceof ApiError && error.status === 403 && error.message.includes('API_TOKEN')) failure = { kind: 'forbidden', message: error.message }
    if (!failure) return
    client.setQueryData(accessKey, failure)
    if (failure.kind !== 'offline') {
      client.setQueryData(authKey, { token_required: true, authenticated: false })
      void client.invalidateQueries({ queryKey: authKey })
    }
  }
  const client = new QueryClient({
    queryCache: new QueryCache({ onError }),
    mutationCache: new MutationCache({ onError }),
    defaultOptions: {
      queries: { networkMode: 'always', retry: (count, error) => !(error instanceof ApiError || error instanceof NetworkError) && count < 1, refetchOnWindowFocus: false },
      mutations: { networkMode: 'always', retry: false },
    },
  })
  return client
}

export async function clearPrivateQueries(client: QueryClient) {
  const filters = { predicate: (query: { queryKey: readonly unknown[] }) => !['auth', 'access-failure'].includes(String(query.queryKey[0])) }
  await client.cancelQueries(filters)
  client.removeQueries(filters)
  client.getMutationCache().clear()
}
