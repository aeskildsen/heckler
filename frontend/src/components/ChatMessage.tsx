export interface MessageData {
  type: string
  content: string
  caption?: string
}

export default function ChatMessage({ data, time }: { data: MessageData, time: string }) {
  
  let content
  if (data.type === 'text') {
    content = <div className="chatMessage">{data.content}</div>
  } else if (data.type === 'meme') {
    content = (<div className="chatMessage">
      <img src={"data:image/png;base64," + data.content} width="100%" />
      {data.caption && <caption>{data.caption}</caption>}
    </div>)
  }

  return (
    <>
      <div className="messageWrapper">
      {content}
      </div>
      <div className="timeStamp">{time}</div>
    </>
  )
}
