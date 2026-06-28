"use client";

import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";

function RedirectContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const corpusId = searchParams.get("id") ?? "";

  useEffect(() => {
    if (corpusId) {
      router.replace(`/inszenierung?id=${corpusId}` as "/inszenierung");
    } else {
      router.replace("/inszenierung");
    }
  }, [router, corpusId]);

  return <main className="container"><p className="textFaint">Weiterleitung …</p></main>;
}

export default function VorbereitenRedirectPage() {
  return (
    <Suspense fallback={<main className="container"><p className="textFaint">Lade …</p></main>}>
      <RedirectContent />
    </Suspense>
  );
}
