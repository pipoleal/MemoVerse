import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: [
        "/dashboard",
        "/checkout",
        "/admin",
        "/experience/edit",
        // Personal experience links (photos, letters) are meant to be
        // shared directly by their owner, not discovered via search —
        // same reasoning as leaving them out of sitemap.ts.
        "/e/",
        // Temporary launch landing (see middleware.ts + lib/launch.ts) —
        // "/" transparently serves this content pre-launch, but the route
        // itself is not meant to be indexed as its own permanent URL; it
        // would just go stale once the real launch happens.
        "/coming-soon",
      ],
    },
    sitemap: "https://memoverse.com.br/sitemap.xml",
  };
}
