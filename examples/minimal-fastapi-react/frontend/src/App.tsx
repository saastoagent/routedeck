import { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { RouteDeckDebugger, type RouteDeckManifest, type RouteDeckRuntimeSnapshot } from '@routedeck/react'
import './style.css'

function App() {
  const [manifest, setManifest] = useState<RouteDeckManifest | null>(null)
  const [snapshot, setSnapshot] = useState<RouteDeckRuntimeSnapshot | null>(null)
  const [selectedNode, setSelectedNode] = useState<string | null>('intent')

  useEffect(() => {
    void fetch('/manifest')
      .then((response) => response.json())
      .then((data) => setManifest(data.manifest))
    void fetch('/snapshot?current_node=intent')
      .then((response) => response.json())
      .then((data) => setSnapshot(data))
  }, [])

  return (
    <main className="app-shell">
      <header>
        <h1>RouteDeck Minimal Example</h1>
        <p>Manifest, runtime snapshot, valid actions, blocked actions, and exportable debugger.</p>
      </header>
      <RouteDeckDebugger
        graphManifest={manifest}
        snapshot={snapshot}
        selectedNodeId={selectedNode}
        onSelectedNodeChange={setSelectedNode}
        runId="example-run"
        sessionId="example-session"
      />
    </main>
  )
}

createRoot(document.getElementById('root')!).render(<App />)
