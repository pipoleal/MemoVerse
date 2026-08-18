from functools import lru_cache

import boto3
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def r2_is_configured() -> bool:
    return all((
        settings.R2_ACCOUNT_ID,
        settings.R2_ACCESS_KEY_ID,
        settings.R2_SECRET_ACCESS_KEY,
        settings.R2_BUCKET_NAME,
    ))


@lru_cache
def get_r2_client():
    if not r2_is_configured():
        raise ImproperlyConfigured("Cloudflare R2 is not configured.")

    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def generate_presigned_read_url(storage_key: str, *, expires_in: int | None = None) -> str:
    """Gera uma URL temporária de LEITURA (GET) para um objeto do bucket R2.

    Infraestrutura pura: recebe só a chave do objeto, não sabe o que é
    Media/ExperienceDraft nem decide se o chamador tem permissão para ler
    aquele objeto — quem decide isso é a camada de autorização/negócio de
    quem chamar esta função (fora de escopo aqui de propósito).

    Nunca torna o objeto público: a URL expira e nenhuma credencial do R2
    (access key, secret, nome do bucket) é exposta nela nem no valor
    retornado — a assinatura fica embutida na própria query string da URL,
    do mesmo jeito que já acontece com a URL de upload gerada em
    MediaUploadIntentView.

    expires_in: mesma variável já usada para o upload
    (R2_PRESIGNED_URL_TTL_SECONDS) por padrão — nenhuma env var nova, já que
    o projeto não tem hoje uma distinção de TTL entre leitura e escrita.
    """

    return get_r2_client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.R2_BUCKET_NAME,
            "Key": storage_key,
        },
        ExpiresIn=expires_in if expires_in is not None else settings.R2_PRESIGNED_URL_TTL_SECONDS,
    )


def delete_object(storage_key: str) -> None:
    """Remove um objeto do bucket R2.

    Idempotente pela própria semântica do protocolo S3: um DeleteObject
    sobre uma chave que já não existe também retorna sucesso (204), nunca
    um erro de "not found" — não há necessidade de checar existência antes
    de chamar isto.

    Infraestrutura pura, como generate_presigned_read_url: não sabe o que é
    Media/ExperienceDraft, não decide autorização. Pode levantar
    ImproperlyConfigured (R2 não configurado) ou ClientError (falha real de
    rede/credencial) — quem chama decide se isso deve ou não impedir a
    remoção do registro correspondente no banco (ver views.MediaDeleteView
    e services.media_cleanup: em ambos, best-effort — nunca bloqueia).
    """

    get_r2_client().delete_object(Bucket=settings.R2_BUCKET_NAME, Key=storage_key)
