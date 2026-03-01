import { useEffect } from 'react'
import ProjectList from './components/Dashboard/ProjectList'
import ProfileToggle from './components/Dashboard/ProfileToggle'
import ChatPanel from './components/Chat/ChatPanel'
import SystemPanel from './components/SystemMonitor/SystemPanel'
import { useAppStore } from './stores'
import './App.css'

function App() {
  const { sidebarOpen, toggleSidebar, selectedProject, projects, agents } = useAppStore()

  const proj = selectedProject ? projects.find(p => p.name === selectedProject) : null
  const projAgents = selectedProject
    ? agents.filter(a => a.project === selectedProject && a.status === 'running')
    : []

  // ESC closes drawer
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && sidebarOpen) toggleSidebar()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [sidebarOpen, toggleSidebar])

  return (
    <div className="h-screen bg-gray-950 text-white flex flex-col">
      {/* Top bar */}
      <header className="h-12 flex items-center border-b border-gray-800 shrink-0">
        {/* Left: hamburger + title */}
        <div className="flex items-center gap-2 px-4">
          <button
            onClick={toggleSidebar}
            className="text-xl w-8 h-8 flex items-center justify-center rounded hover:bg-gray-800 transition-colors"
            aria-label="Toggle sidebar"
          >
            &#9776;
          </button>
          <h1 className="text-base font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent whitespace-nowrap">
            Gypsea
          </h1>
        </div>

        {/* Right: project info + profile */}
        <div className="ml-auto flex items-center gap-2 px-4">
          {proj && (
            <>
              {proj.git?.branch && (
                <span className="text-xs text-purple-400 hidden md:block">{proj.git.branch}</span>
              )}
              <span className="text-xs text-gray-600 hidden md:block">{proj.server}</span>
              <span className="px-1.5 py-0.5 text-[11px] bg-gray-800 text-gray-500 rounded hidden sm:block">
                {proj.stack}
              </span>
              {projAgents.length > 0 && (
                <span className="px-1.5 py-0.5 text-[11px] bg-green-500/15 text-green-400 rounded">
                  {projAgents.length} agent{projAgents.length > 1 ? 's' : ''}
                </span>
              )}
              <span className="text-sm font-medium text-white pl-2 border-l border-gray-800">
                {selectedProject}
              </span>
            </>
          )}
          <div className="pl-2 border-l border-gray-800">
            <ProfileToggle />
          </div>
        </div>
      </header>

      {/* Content area */}
      <div className="flex-1 relative overflow-hidden">
        {/* Backdrop */}
        <div
          className={`backdrop ${sidebarOpen ? 'backdrop-visible' : ''}`}
          onClick={toggleSidebar}
        />

        {/* Drawer */}
        <aside className={`drawer ${sidebarOpen ? 'drawer-open' : ''}`}>
          <div className="flex-1 overflow-y-auto p-3">
            <ProjectList />
          </div>
          <div className="border-t border-gray-800">
            <SystemPanel />
          </div>
        </aside>

        {/* Main: Chat full width */}
        <main className="h-full flex flex-col overflow-hidden">
          <ChatPanel />
        </main>
      </div>
    </div>
  )
}

export default App
