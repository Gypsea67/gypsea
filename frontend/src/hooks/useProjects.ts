import { useEffect, useCallback } from 'react'
import { useAppStore, type ProjectStatus } from '../stores'
import { apiFetch } from './useSSE'

export function useProjects() {
  const { projects, setProjects, selectedProject, selectProject } = useAppStore()

  const refresh = useCallback(async () => {
    try {
      const data = await apiFetch<ProjectStatus[]>('/api/projects/')
      setProjects(data)
    } catch (err) {
      console.error('Failed to fetch projects:', err)
    }
  }, [setProjects])

  useEffect(() => {
    refresh()
    const interval = setInterval(refresh, 30000) // Refresh every 30s
    return () => clearInterval(interval)
  }, [refresh])

  return { projects, selectedProject, selectProject, refresh }
}
