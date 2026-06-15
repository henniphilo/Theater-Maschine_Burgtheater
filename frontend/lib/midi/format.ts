export function midiNoteLabel(note: number): string {
  const names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
  const octave = Math.floor(note / 12) - 1;
  return `${names[note % 12]}${octave}`;
}

export function formatMidiTrigger(note: number, channel: number): string {
  return `Note ${note} ch=${channel} (${midiNoteLabel(note)})`;
}
