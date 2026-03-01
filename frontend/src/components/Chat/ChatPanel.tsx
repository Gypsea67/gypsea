import { useState, useRef, useEffect } from 'react'
import { useAppStore } from '../../stores'
import { apiFetch, useSSE } from '../../hooks/useSSE'

export default function ChatPanel() {
  const { selectedProject, chatHistory, addChatMessage, setStreamActive } = useAppStore()
  const [input, setInput] = useState('')
  const [currentAgentId, setCurrentAgentId] = useState<string | null>(null)
  const [streamOutput, setStreamOutput] = useState('')
  const streamRef = useRef('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const messages = selectedProject ? chatHistory[selectedProject] || [] : []

  // SSE stream for agent output
  // streamRef — накопитель, чтобы не терять данные между рендерами
  useSSE(
    currentAgentId ? `/api/chat/stream/${currentAgentId}` : '',
    (data) => {
      if (data.type === 'done' || data.type === 'finished') {
        if (selectedProject && streamRef.current) {
          addChatMessage(selectedProject, {
            role: 'assistant',
            content: streamRef.current,
            agent_id: currentAgentId || undefined,
          })
        }
        streamRef.current = ''
        setStreamOutput('')
        setCurrentAgentId(null)
        if (currentAgentId) setStreamActive(currentAgentId, false)
      } else if (data.type === 'token' || data.type === 'raw') {
        streamRef.current += data.data
        setStreamOutput(streamRef.current)
      }
    },
    !!currentAgentId
  )

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamOutput])

  const sendMessage = async () => {
    console.log('[Gypsea] sendMessage called', { input: input.trim(), selectedProject, currentAgentId })
    if (!input.trim() || !selectedProject) return

    const prompt = input.trim()
    setInput('')

    addChatMessage(selectedProject, { role: 'user', content: prompt })

    try {
      console.log('[Gypsea] Sending to API...')
      const res = await apiFetch('/api/chat/send', {
        method: 'POST',
        body: JSON.stringify({ project: selectedProject, prompt, model: 'sonnet' }),
      })
      console.log('[Gypsea] API response:', res)

      if (res.error) {
        addChatMessage(selectedProject, { role: 'assistant', content: `Error: ${res.error}` })
      } else {
        setCurrentAgentId(res.agent_id)
        setStreamActive(res.agent_id, true)
      }
    } catch (err) {
      console.error('[Gypsea] Send error:', err)
      addChatMessage(selectedProject, {
        role: 'assistant',
        content: `Connection error: ${err}`,
      })
    }
  }

  if (!selectedProject) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500">
        Select a project to start chatting
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] rounded-lg px-4 py-2 ${
              msg.role === 'user'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-800 text-gray-200'
            }`}>
              <pre className="whitespace-pre-wrap font-mono text-sm">{msg.content}</pre>
            </div>
          </div>
        ))}

        {/* Streaming output */}
        {streamOutput && (
          <div className="flex justify-start">
            <div className="max-w-[80%] rounded-lg px-4 py-2 bg-gray-800 text-gray-200 border border-green-500/30">
              <pre className="whitespace-pre-wrap font-mono text-sm">{streamOutput}</pre>
              <span className="inline-block w-2 h-4 bg-green-500 animate-pulse ml-1" />
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-gray-700">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
            placeholder={`Message ${selectedProject}...`}
            className="flex-1 bg-gray-800 text-white rounded-lg px-4 py-2 outline-none focus:ring-2 focus:ring-blue-500"
            disabled={!!currentAgentId}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || !!currentAgentId}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {currentAgentId ? 'Running...' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  )
}
