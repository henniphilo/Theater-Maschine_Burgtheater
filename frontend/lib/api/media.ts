import type { MediaCatalog } from "@/lib/types/media";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export type VideoScope = "part1" | "part2";

export async function fetchMediaCatalog(videoScope: VideoScope = "part2"): Promise<MediaCatalog> {
  const res = await fetch(`${API_BASE}/media/catalog?video_scope=${videoScope}`);
  if (!res.ok) throw new Error("Media catalog unavailable");
  return res.json();
}
