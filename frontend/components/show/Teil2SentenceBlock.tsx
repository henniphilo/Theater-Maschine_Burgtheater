type Teil2SentenceBlockProps = {
  sentence: string;
  index: number;
  active?: boolean;
  clickable?: boolean;
  onSelect?: () => void;
};

export function Teil2SentenceBlock({
  sentence,
  index,
  active = false,
  clickable = false,
  onSelect
}: Teil2SentenceBlockProps) {
  const preview = sentence.length > 280 ? `${sentence.slice(0, 280)}…` : sentence;

  if (clickable && onSelect) {
    return (
      <button
        type="button"
        className={`teil2SentenceBlock teil2SentenceBlockButton${active ? " teil2SentenceBlockActive" : ""}`}
        onClick={onSelect}
        aria-label={`Ab Satz ${index + 1} abspielen`}
      >
        <p className="teil2SentenceText">{preview}</p>
      </button>
    );
  }

  return (
    <article className={`teil2SentenceBlock${active ? " teil2SentenceBlockActive" : ""}`}>
      <p className="teil2SentenceText">{preview}</p>
    </article>
  );
}
