# Semaforómetro Digital

## Estructura
- `api/index.py` → toda la app
- `vercel.json` → manda todas las rutas a la app
- `.gitignore`

## Subir a Vercel
1. Subí esta carpeta a un repo de GitHub e importalo en vercel.com (o usá `vercel` desde la terminal).
2. En el proyecto: **Storage → Marketplace → Upstash Redis → Create**, y conectalo al proyecto.
   Eso crea solas las variables `KV_REST_API_URL` y `KV_REST_API_TOKEN`.
3. **Redeploy** para que tome las variables.

Páginas: `/` (encuesta) y `/resultados` (contador en vivo).
Sin Redis los contadores no se guardan bien en Vercel (se reinician).
