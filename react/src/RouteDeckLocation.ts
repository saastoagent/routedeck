import type {
  RouteDeckHistoryAdapter,
  RouteDeckLocation,
  RouteDeckLocationCodec,
  RouteDeckUrl,
} from './types'

export interface RouteDeckHistoryLocationOptions {
  adapter: RouteDeckHistoryAdapter
  codec: RouteDeckLocationCodec
}

export interface RouteDeckHistoryWriteOptions extends RouteDeckHistoryLocationOptions {
  location: RouteDeckLocation
  mode?: 'push' | 'replace'
}

export interface BrowserHistoryLike {
  location: {
    pathname: string
    search: string
    hash: string
  }
  history: {
    pushState: (data: unknown, unused: string, url?: string | URL | null) => void
    replaceState: (data: unknown, unused: string, url?: string | URL | null) => void
    state: unknown
  }
  addEventListener: (type: 'popstate', listener: () => void) => void
  removeEventListener: (type: 'popstate', listener: () => void) => void
}

export function routeDeckUrlString(url: RouteDeckUrl): string {
  return `${url.pathname}${url.search || ''}${url.hash || ''}`
}

export function readRouteDeckHistoryLocation({
  adapter,
  codec,
}: RouteDeckHistoryLocationOptions): RouteDeckLocation | null {
  return codec.decode(adapter.read())
}

export function writeRouteDeckHistoryLocation({
  adapter,
  codec,
  location,
  mode = 'push',
}: RouteDeckHistoryWriteOptions): RouteDeckUrl {
  const url = codec.encode(location)
  if (mode === 'replace') {
    adapter.replace(url)
  } else {
    adapter.push(url)
  }
  return url
}

export function createBrowserRouteDeckHistoryAdapter(browser: BrowserHistoryLike = window): RouteDeckHistoryAdapter {
  return {
    read: () => ({
      pathname: browser.location.pathname,
      search: browser.location.search,
      hash: browser.location.hash,
    }),
    push: (url) => browser.history.pushState(browser.history.state, '', routeDeckUrlString(url)),
    replace: (url) => browser.history.replaceState(browser.history.state, '', routeDeckUrlString(url)),
    subscribe: (listener) => {
      browser.addEventListener('popstate', listener)
      return () => browser.removeEventListener('popstate', listener)
    },
  }
}
