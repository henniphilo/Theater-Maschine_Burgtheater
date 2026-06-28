import type { MediaCatalog } from "@/lib/types/media";
import { apiFetch } from "@/lib/api/base";

export type VideoScope = "part1" | "part2";

export async function fetchMediaCatalog(videoScope: VideoScope = "part2"): Promise<MediaCatalog> {
  const res = await apiFetch(`/media/catalog?video_scope=${videoScope}`);
  if (!res.ok) throw new Error("Media catalog unavailable");
  return res.json();
}
