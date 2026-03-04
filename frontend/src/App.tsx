import ChatMessage from './components/ChatMessage'
import Header from './components/Header'
import type { MessageData } from './components/ChatMessage'

import { useState, useEffect, useRef } from 'react'
import TypingIndicator from './components/TypingIndicator'

interface Message {
  id: string
  data: MessageData
  time: string
}

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const chatboxRef = useRef<HTMLDivElement>(null)
  const wsRef = useRef<WebSocket | null>(null)

  const typingTimeout = 3000; // milliseconds

  const [isTyping, setIsTyping] = useState(false);

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8765')
    wsRef.current = ws

    ws.onmessage = (event) => {
      console.log('Message from server ', event.data)
      const data = JSON.parse(event.data)

      // Handle clear command from server
      if (data.type === 'clear') {
        console.log('Received clear command from server')
        setMessages([])
        setIsTyping(false)
        return
      }

      // Handle regular messages
      const time = new Date()
      const hours = time.getHours()
      const minutes = time.getMinutes().toString().padStart(2, '0')
      const messageWithTime: Message = {
        id: `${Date.now()}-${Math.random()}`,
        data: data,
        time: `${hours}:${minutes}`
      }

      setIsTyping(true);

      setTimeout(() => {
        setIsTyping(false);
        setMessages((prevMessages) => [...prevMessages, messageWithTime])
      }, typingTimeout);
    }

    return () => {
      ws.close()
    }
  }, [])

  const handleClear = () => {
    console.log('Clear button clicked')
    // Send clear command to server
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ command: 'clear' }))
    }
    // Clear local messages immediately
    setMessages([])
    setIsTyping(false)
  }

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (chatboxRef.current) {
      chatboxRef.current.scrollTop = chatboxRef.current.scrollHeight
    }
  }, [messages, isTyping])


  return (
    <>
      <main>
        <Header onClear={handleClear} />
        <div className="chatbox" ref={chatboxRef}>
          {messages.map((message) => (
            <ChatMessage key={message.id} time={message.time} data={message.data} />
          ))}
          <TypingIndicator active={isTyping} />
        </div>
      </main>

    </>
  )
}

export default App
