import type { AvatarTextSegment } from "@/lib/types/inszenierung";

export function avatarSegmentLabel(segment: AvatarTextSegment): string {
  const names = segment.avatar_layers.map((layer) => layer.video_clip_id || layer.avatar);
  return names.length > 0 ? names.join(" · ") : segment.csv_cue_ids.join(", ");
}

export function activeAvatarSegmentIndex(
  segments: AvatarTextSegment[],
  sentenceIndex: number
): number {
  if (sentenceIndex < 0) return -1;
  return segments.findIndex(
    (segment) =>
      sentenceIndex >= segment.start_sentence_index && sentenceIndex <= segment.end_sentence_index
  );
}
