export default function ChatMessage({ children, time }: { children: React.ReactNode, time: string }) {
  
  return (
    <>
      <div className="timeStamp">{time}</div>
      <span className="chatMessage">{children}</span>
    </>
  )
}
