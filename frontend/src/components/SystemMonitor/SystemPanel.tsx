import { useState } from 'react'
import { useAppStore } from '../../stores'
import { useSSE } from '../../hooks/useSSE'

export default function SystemPanel() {
  const { system, setSystem } = useAppStore()
  const [isCollapsed, setIsCollapsed] = useState(false)

  // SSE для system events
  useSSE('/api/events/stream', (data) => {
    if (data.ram_percent !== undefined) {
      setSystem(data)
    }
  })

  const zoneColors = {
    green: 'bg-green-500',
    yellow: 'bg-yellow-500',
    red: 'bg-red-500',
  }

  const zoneTextColors = {
    green: 'text-green-400',
    yellow: 'text-yellow-400',
    red: 'text-red-400',
  }

  return (
    <div className="p-4">
      <button
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="flex items-center justify-between w-full text-lg font-semibold text-gray-200 hover:text-white transition-colors"
      >
        <span>System</span>
        <span className="text-sm text-gray-500">{isCollapsed ? '\u25B8' : '\u25BE'}</span>
      </button>

      <div className={`collapsible-content ${isCollapsed ? 'collapsed' : ''}`}>
        {!system ? (
          <div className="pt-3 text-gray-500">Connecting to system monitor...</div>
        ) : (
          <div className="pt-3 space-y-4">
            {/* RAM Gauge */}
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">RAM</span>
                <span className={zoneTextColors[system.ram_zone]}>
                  {system.ram_used_mb} / {system.ram_total_mb} MB ({system.ram_percent}%)
                </span>
              </div>
              <div className="w-full h-3 bg-gray-700 rounded-full overflow-hidden">
                <div
                  className={`h-full ${zoneColors[system.ram_zone]} transition-all duration-500`}
                  style={{ width: `${Math.min(system.ram_percent, 100)}%` }}
                />
              </div>
            </div>

            {/* CPU */}
            <div className="flex justify-between text-sm">
              <span className="text-gray-400">CPU Load</span>
              <span className="text-gray-200">{system.cpu_percent}%</span>
            </div>

            {/* Claude Processes */}
            <div className="flex justify-between text-sm">
              <span className="text-gray-400">Claude Processes</span>
              <span className="text-gray-200">{system.claude_processes} ({system.claude_ram_mb} MB)</span>
            </div>

            {/* Spawn status */}
            <div className={`text-center py-2 rounded-lg text-sm ${
              system.ram_zone === 'red'
                ? 'bg-red-500/20 text-red-400'
                : system.ram_zone === 'yellow'
                ? 'bg-yellow-500/20 text-yellow-400'
                : 'bg-green-500/20 text-green-400'
            }`}>
              {system.ram_zone === 'red'
                ? 'Agent spawn blocked (RAM > 80%)'
                : system.ram_zone === 'yellow'
                ? 'Warning: RAM 60-80%'
                : 'Ready to spawn agents'}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
