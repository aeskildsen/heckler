import ChatMessage from './components/ChatMessage'
import Header from './components/Header'

import { useState, useEffect } from 'react'

interface Message {
  text: string
  time: string
}

function App() {
  const [messages, setMessages] = useState<Message[]>([{ text: 'Welcome to Heckler! Start the backend to receive messages.', time: '00.00' }])

  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8765')
    ws.onmessage = (event) => {
      console.log('Message from server ', event.data)
      const time = new Date()
      const hours = time.getHours()
      const minutes = time.getMinutes().toString().padStart(2, '0')

      const messageWithTime = {
        text: JSON.parse(event.data).content,
        time: `${hours}:${minutes}`
      }
      setMessages((prevMessages) => [ messageWithTime, ...prevMessages])
    }
    return () => {
      ws.close()
    }
  }, [])

  return (
    <>
      <Header />
      <div className="chatbox">
        {messages.map((message) => (
          <ChatMessage time={message.time}>{message.text}</ChatMessage>
          
        ))}
      </div>

    </>
  )
}

export default App
