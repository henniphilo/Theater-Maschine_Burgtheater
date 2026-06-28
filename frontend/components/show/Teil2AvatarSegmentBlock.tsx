import { avatarSegmentLabel } from "@/features/inszenierung/teil2AvatarSections";
import type { AvatarTextSegment } from "@/lib/types/inszenierung";

type Teil2AvatarSegmentBlockProps = {
  segment: AvatarTextSegment;
  index: number;
  active?: boolean;
  clickable?: boolean;
  onSelect?: () => void;
};

export function Teil2AvatarSegmentBlock({
  segment,
  index,
  active = false,
  clickable = false,
  onSelect
}: Teil2AvatarSegmentBlockProps) {
  const label = avatarSegmentLabel(segment);
  const text = segment.text_excerpt.trim();
  const preview = text.length > 320 ? `${text.slice(0, 320)}…` : text;

  const content = (
    <>
      <header className="teil2SegmentHeader">
        <strong>{label}</strong>
        {segment.avatar_layers.length > 1 ? (
          <span className="textMuted"> · Chorus ({segment.avatar_layers.length})</span>
        ) : null}
      </header>
      <p className="teil2SentenceText">{preview}</p>
    </>
  );

  if (clickable && onSelect) {
    return (
      <button
        type="button"
        className={`teil2SentenceBlock teil2SentenceBlockButton${active ? " teil2SentenceBlockActive" : ""}`}
        onClick={onSelect}
        aria-label={`Abschnitt ${index + 1} (${label}) abspielen`}
      >
        {content}
      </button>
    );
  }

  return (
    <article className={`teil2SentenceBlock${active ? " teil2SentenceBlockActive" : ""}`}>{content}</article>
  );
}
