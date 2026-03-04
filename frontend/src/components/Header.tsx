interface HeaderProps {
  onClear: () => void
}

export default function Header({ onClear }: HeaderProps) {
  return (
    <header className="header">
    	<button
          onClick={onClear}
          className="clear-button"
          title="Clear chat and reset context"
        >
          Clear
        </button>
      <div className="title">
        <h2>Heckler</h2>
        <p>Snarky live coding companion</p>
      </div>
      <img className="profile" src="heckler.jpg" alt="Profile photo" width="80px" />
    </header>
  )
}
