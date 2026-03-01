import { useProjects } from '../../hooks/useProjects'
import { useAppStore } from '../../stores'
import type { ProjectStatus } from '../../stores'

function ProjectCard({ project, selected, onClick }: {
  project: ProjectStatus
  selected: boolean
  onClick: () => void
}) {
  const statusColor = project.hot ? 'border-red-500' : 'border-gray-700'
  const gitBranch = project.git?.branch || '—'
  const gitChanges = (project.git?.modified || 0) + (project.git?.untracked || 0) + (project.git?.staged || 0)

  return (
    <div
      onClick={onClick}
      className={`p-4 rounded-lg border-2 cursor-pointer transition-all hover:border-blue-500 ${
        selected ? 'border-blue-500 bg-blue-500/10' : `${statusColor} bg-gray-900`
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-bold text-white">{project.name}</h3>
        <div className="flex gap-2">
          {project.hot && (
            <span className="px-2 py-0.5 text-xs bg-red-500/20 text-red-400 rounded">HOT</span>
          )}
          <span className="px-2 py-0.5 text-xs bg-gray-700 text-gray-300 rounded">{project.stack}</span>
        </div>
      </div>

      <div className="text-sm text-gray-400 space-y-1">
        <div className="flex justify-between">
          <span>{gitBranch}</span>
          {gitChanges > 0 && (
            <span className="text-yellow-400">{gitChanges} changes</span>
          )}
        </div>
        <div className="flex justify-between">
          <span>{project.server}</span>
          {project.active_agents > 0 && (
            <span className="text-green-400">{project.active_agents} agent(s)</span>
          )}
        </div>
        {project.git?.error && (
          <div className="text-red-400 text-xs">{project.git.error}</div>
        )}
      </div>
    </div>
  )
}

export default function ProjectList() {
  const { projects, selectedProject, selectProject } = useProjects()
  const { sidebarOpen, toggleSidebar } = useAppStore()

  const handleSelect = (name: string) => {
    selectProject(name)
    if (sidebarOpen) toggleSidebar()
  }

  if (!projects.length) {
    return (
      <div className="p-8 text-center text-gray-500">
        Loading projects...
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <h2 className="text-lg font-semibold text-gray-200 px-1">Projects</h2>
      {projects.map((p) => (
        <ProjectCard
          key={p.name}
          project={p}
          selected={selectedProject === p.name}
          onClick={() => handleSelect(p.name)}
        />
      ))}
    </div>
  )
}
