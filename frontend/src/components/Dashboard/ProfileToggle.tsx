import { useEffect, useCallback } from 'react'
import { useAppStore, type ProfileInfo } from '../../stores'
import { apiFetch } from '../../hooks/useSSE'

export default function ProfileToggle() {
  const { profileInfo, setProfileInfo } = useAppStore()

  const fetchProfiles = useCallback(async () => {
    try {
      const data = await apiFetch<ProfileInfo>('/api/config/profiles')
      setProfileInfo(data)
    } catch (err) {
      console.error('Failed to fetch profiles:', err)
    }
  }, [setProfileInfo])

  useEffect(() => {
    fetchProfiles()
  }, [fetchProfiles])

  const switchProfile = async (name: string) => {
    try {
      await apiFetch('/api/config/profile', {
        method: 'POST',
        body: JSON.stringify({ profile: name }),
      })
      await fetchProfiles()
      // Trigger projects refresh by invalidating store
      const { setProjects } = useAppStore.getState()
      const projects = await apiFetch('/api/projects/')
      setProjects(projects)
    } catch (err) {
      console.error('Failed to switch profile:', err)
    }
  }

  if (!profileInfo) return null

  return (
    <div className="flex items-center gap-1">
      {profileInfo.profiles.map((name) => (
        <button
          key={name}
          onClick={() => switchProfile(name)}
          className={`px-2 py-0.5 text-xs rounded transition-colors ${
            profileInfo.active === name
              ? 'bg-blue-500 text-white'
              : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
          }`}
        >
          {name}
        </button>
      ))}
    </div>
  )
}
