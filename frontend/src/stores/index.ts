import { create } from 'zustand'

// === Types ===

export interface GitStatus {
  branch: string
  modified: number
  untracked: number
  staged: number
  ahead: number
  behind: number
  last_commit: string
  last_commit_time: string
  error?: string
}

export interface ProjectStatus {
  name: string
  path: string
  server: string
  stack: string
  priority: string
  hot: boolean
  git?: GitStatus
  active_agents: number
  last_deploy?: string
}

export interface SystemInfo {
  ram_total_mb: number
  ram_used_mb: number
  ram_percent: number
  ram_zone: 'green' | 'yellow' | 'red'
  cpu_percent: number
  claude_processes: number
  claude_ram_mb: number
}

export interface Agent {
  agent_id: string
  project: string
  status: string
  pid?: number
  started_at?: string
  last_heartbeat?: string
  last_output?: string
  task_description: string
  model: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  agent_id?: string
  timestamp?: string
}

export interface ProfileInfo {
  active: string
  configured: string
  profiles: string[]
}

// === Store ===

interface AppState {
  // Projects
  projects: ProjectStatus[]
  selectedProject: string | null
  setProjects: (projects: ProjectStatus[]) => void
  selectProject: (name: string | null) => void

  // Profile
  profileInfo: ProfileInfo | null
  setProfileInfo: (info: ProfileInfo) => void

  // System
  system: SystemInfo | null
  setSystem: (info: SystemInfo) => void

  // Agents
  agents: Agent[]
  setAgents: (agents: Agent[]) => void

  // Chat
  chatHistory: Record<string, ChatMessage[]>
  addChatMessage: (project: string, msg: ChatMessage) => void
  setChatHistory: (project: string, messages: ChatMessage[]) => void

  // Sidebar
  sidebarOpen: boolean
  toggleSidebar: () => void

  // Active streams
  activeStreams: Record<string, boolean>
  setStreamActive: (agentId: string, active: boolean) => void
}

export const useAppStore = create<AppState>((set) => ({
  // Projects
  projects: [],
  selectedProject: null,
  setProjects: (projects) => set({ projects }),
  selectProject: (name) => set({ selectedProject: name }),

  // Profile
  profileInfo: null,
  setProfileInfo: (info) => set({ profileInfo: info }),

  // System
  system: null,
  setSystem: (info) => set({ system: info }),

  // Agents
  agents: [],
  setAgents: (agents) => set({ agents }),

  // Chat
  chatHistory: {},
  addChatMessage: (project, msg) =>
    set((state) => ({
      chatHistory: {
        ...state.chatHistory,
        [project]: [...(state.chatHistory[project] || []), msg],
      },
    })),
  setChatHistory: (project, messages) =>
    set((state) => ({
      chatHistory: { ...state.chatHistory, [project]: messages },
    })),

  // Sidebar
  sidebarOpen: false,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),

  // Streams
  activeStreams: {},
  setStreamActive: (agentId, active) =>
    set((state) => ({
      activeStreams: { ...state.activeStreams, [agentId]: active },
    })),
}))
