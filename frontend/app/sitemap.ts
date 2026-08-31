import type { MetadataRoute } from "next";

// Only static, public marketing routes. Deliberately NOT listing /e/[slug]
// pages: those are personal experiences belonging to individual users, and
// enumerating every published one in a public sitemap would expose private
// links to search engines that were only ever meant to be shared directly
// by their owner.
export default function sitemap(): MetadataRoute.Sitemap {
  const base = "https://memoverse.com.br";

  return [
    { url: base, changeFrequency: "monthly", priority: 1 },
    { url: `${base}/sobre`, changeFrequency: "yearly", priority: 0.4 },
    { url: `${base}/termos-de-uso`, changeFrequency: "yearly", priority: 0.2 },
    { url: `${base}/politica-de-privacidade`, changeFrequency: "yearly", priority: 0.2 },
    { url: `${base}/login`, changeFrequency: "yearly", priority: 0.3 },
    { url: `${base}/register`, changeFrequency: "yearly", priority: 0.5 },
  ];
}
