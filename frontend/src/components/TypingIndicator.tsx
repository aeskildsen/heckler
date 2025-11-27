export default function TypingIndicator({ active }: { active: boolean }) {
    return (
    <div className={`typing-indicator ${active ? 'active' : ''}`}>
      <span className="dot"></span>
      <span className="dot"></span>
      <span className="dot"></span>
    </div>
  )
}