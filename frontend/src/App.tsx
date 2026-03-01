import { useEffect } from 'react'
import ProjectList from './components/Dashboard/ProjectList'
import ProfileToggle from './components/Dashboard/ProfileToggle'
import ChatPanel from './components/Chat/ChatPanel'
import SystemPanel from './components/SystemMonitor/SystemPanel'
import { useAppStore } from './stores'
import './App.css'

const CHATCLAW_URL = 'http://localhost:3000'

function App() {
  const {
    sidebarOpen, toggleSidebar,
    selectedProject, projects, agents,
    activeTab, setActiveTab,
    chatclawFullscreen, toggleChatclawFullscreen,
  } = useAppStore()

  const proj = selectedProject ? projects.find(p => p.name === selectedProject) : null
  const projAgents = selectedProject
    ? agents.filter(a => a.project === selectedProject && a.status === 'running')
    : []

  // ESC closes drawer or exits fullscreen
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (chatclawFullscreen) toggleChatclawFullscreen()
        else if (sidebarOpen) toggleSidebar()
      }
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [sidebarOpen, toggleSidebar, chatclawFullscreen, toggleChatclawFullscreen])

  const isFullscreen = chatclawFullscreen && activeTab === 'chatclaw'

  if (isFullscreen) {
    return (
      <div className="h-screen bg-gray-950 text-white flex flex-col">
        {/* Thin top strip with exit button */}
        <div className="h-8 flex items-center bg-gray-900/80 border-b border-gray-800 shrink-0 px-3 gap-2">
          <button
            onClick={toggleChatclawFullscreen}
            className="px-2.5 py-0.5 text-[11px] font-medium bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-white rounded transition-colors"
          >
            &#x2715; Exit fullscreen
          </button>
          <span className="text-[11px] text-gray-600">Esc</span>
        </div>
        <iframe
          src={CHATCLAW_URL}
          className="flex-1 w-full border-0"
          title="ChatClaw"
        />
      </div>
    )
  }

  return (
    <div className="h-screen bg-gray-950 text-white flex flex-col">
      {/* Top bar */}
      <header className="h-12 flex items-center border-b border-gray-800 shrink-0">
        {/* Left: hamburger + title + tabs */}
        <div className="flex items-center gap-1 px-4">
          <button
            onClick={toggleSidebar}
            className="text-xl w-8 h-8 flex items-center justify-center rounded hover:bg-gray-800 transition-colors"
            aria-label="Toggle sidebar"
          >
            &#9776;
          </button>
          <h1 className="text-base font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent whitespace-nowrap mr-3">
            Gypsea
          </h1>

          {/* Tabs */}
          <div className="flex items-center bg-gray-900 rounded-lg p-0.5">
            <button
              onClick={() => setActiveTab('chat')}
              className={`px-3 py-1 text-xs rounded-md transition-colors ${
                activeTab === 'chat'
                  ? 'bg-gray-700 text-white'
                  : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              Chat
            </button>
            <button
              onClick={() => setActiveTab('chatclaw')}
              className={`px-3 py-1 text-xs rounded-md transition-colors ${
                activeTab === 'chatclaw'
                  ? 'bg-gray-700 text-white'
                  : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              ChatClaw
            </button>
          </div>

          {activeTab === 'chatclaw' && (
            <button
              onClick={toggleChatclawFullscreen}
              className="ml-2 px-2 py-0.5 text-[11px] font-medium bg-gray-800 hover:bg-gray-700 text-gray-500 hover:text-white rounded transition-colors"
            >
              Fullscreen
            </button>
          )}
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

        {/* Main content — tab switch */}
        <main className="h-full flex flex-col overflow-hidden">
          <div className={`h-full ${activeTab === 'chat' ? '' : 'hidden'}`}>
            <ChatPanel />
          </div>
          <div className={`h-full ${activeTab === 'chatclaw' ? '' : 'hidden'}`}>
            <iframe
              src={CHATCLAW_URL}
              className="w-full h-full border-0"
              title="ChatClaw"
            />
          </div>
        </main>
      </div>
    </div>
  )
}

export default App
