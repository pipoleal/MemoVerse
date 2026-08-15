import axios from "axios";

import { api } from "./api";

export type MediaType = "photo" | "video";

// Mirrors apps/experiences/serializers.py UploadIntentSerializer.validate —
// kept in sync manually since the backend is the single source of truth;
// this is only a fast client-side pre-check, never the final authority.
const ALLOWED_MIME_TYPES: Record<MediaType, string[]> = {
  photo: ["image/jpeg", "image/png", "image/webp"],
  video: ["video/mp4", "video/webm", "video/quicktime"],
};

const MAX_BYTES: Record<MediaType, number> = {
  photo: 20 * 1024 * 1024,
  video: 500 * 1024 * 1024,
};

export function validateFileForUpload(mediaType: MediaType, file: File): string | null {
  if (!ALLOWED_MIME_TYPES[mediaType].includes(file.type)) {
    return "Tipo de arquivo não permitido.";
  }

  if (file.size > MAX_BYTES[mediaType]) {
    return "Arquivo excede o tamanho permitido.";
  }

  return null;
}

type UploadIntentResponse = {
  media_id: string;
  upload_url: string;
  method: string;
  headers: Record<string, string>;
  expires_in: number;
};

function extractErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data;
    if (typeof data?.detail === "string") return data.detail;
    const firstFieldError = data && typeof data === "object" ? Object.values(data)[0] : undefined;
    if (Array.isArray(firstFieldError) && typeof firstFieldError[0] === "string") return firstFieldError[0];
    if (!error.response) return "Não foi possível conectar ao servidor.";
  }

  return fallback;
}

async function requestUploadIntent(draftId: string, mediaType: MediaType, file: File): Promise<UploadIntentResponse> {
  try {
    const response = await api.post<UploadIntentResponse>(`/experiences/drafts/${draftId}/media/upload-intents/`, {
      media_type: mediaType,
      filename: file.name,
      mime_type: file.type,
      size_bytes: file.size,
    });

    return response.data;
  } catch (error) {
    throw new Error(extractErrorMessage(error, "Não foi possível iniciar o envio do arquivo."));
  }
}

// Uploads the file bytes directly to the Cloudflare R2 pre-signed URL —
// never through our own backend. Only the exact headers the backend
// returned are sent; no credentials of any kind touch the browser.
function putFileToPresignedUrl(
  uploadUrl: string,
  file: File,
  headers: Record<string, string>,
  onProgress: (percent: number) => void,
  signal: AbortSignal
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    const onAbort = () => {
      xhr.abort();
    };
    signal.addEventListener("abort", onAbort);

    xhr.open("PUT", uploadUrl, true);
    Object.entries(headers).forEach(([key, value]) => xhr.setRequestHeader(key, value));

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    };

    xhr.onload = () => {
      signal.removeEventListener("abort", onAbort);
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve();
      } else {
        reject(new Error("O armazenamento recusou o arquivo enviado."));
      }
    };

    xhr.onerror = () => {
      signal.removeEventListener("abort", onAbort);
      reject(new Error("Falha de rede ao enviar o arquivo."));
    };

    xhr.onabort = () => {
      signal.removeEventListener("abort", onAbort);
      reject(new DOMException("Upload cancelado.", "AbortError"));
    };

    xhr.send(file);
  });
}

async function confirmUploadComplete(draftId: string, mediaId: string): Promise<void> {
  try {
    await api.post(`/experiences/drafts/${draftId}/media/${mediaId}/complete/`);
  } catch (error) {
    throw new Error(extractErrorMessage(error, "Não foi possível confirmar o upload."));
  }
}

export async function uploadMediaFile(
  draftId: string,
  mediaType: MediaType,
  file: File,
  onProgress: (percent: number) => void,
  signal: AbortSignal
): Promise<string> {
  const intent = await requestUploadIntent(draftId, mediaType, file);

  // Only reachable if the PUT above resolved (2xx from R2) — a failed or
  // aborted upload never reaches confirmUploadComplete.
  await putFileToPresignedUrl(intent.upload_url, file, intent.headers, onProgress, signal);
  await confirmUploadComplete(draftId, intent.media_id);

  return intent.media_id;
}
