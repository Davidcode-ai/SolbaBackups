import json
import logging
import os
import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

# Ruta base compatible con modo frozen (PyInstaller) y modo script
if getattr(sys, 'frozen', False):
    _BASE_DIR = Path(sys.executable).parent
else:
    _BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent

_DEFAULT_CREDENTIALS_PATH = _BASE_DIR / "credentials.json"
_DEFAULT_TOKEN_PATH = _BASE_DIR / "token.json"

# Permitir HTTP para desarrollo local en tiendas
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

_OAUTH_STORE = {}

def _get_flow(redirect_uri: str):
    if not _DEFAULT_CREDENTIALS_PATH.exists():
        raise HTTPException(status_code=404, detail="Archivo credentials.json no encontrado.")
    
    try:
        flow = Flow.from_client_secrets_file(
            str(_DEFAULT_CREDENTIALS_PATH),
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )
        return flow
    except Exception as e:
        log.error(f"Error leyendo credentials.json: {e}")
        raise HTTPException(status_code=500, detail=f"Error leyendo credenciales: {e}")

@router.get("/google/status")
def get_status():
    """Comprueba si la app ya está conectada a Google Drive."""
    if not _DEFAULT_TOKEN_PATH.exists():
        return {"authorized": False}
    try:
        with open(_DEFAULT_TOKEN_PATH, 'r') as f:
            creds_data = json.load(f)
        creds = Credentials.from_authorized_user_info(creds_data, SCOPES)
        
        is_authorized = creds.valid or (creds.expired and creds.refresh_token is not None)
        if not is_authorized:
            return {"authorized": False}
            
        email = "Cuenta Vinculada"
        try:
            if creds.expired and creds.refresh_token:
                from google.auth.transport.requests import Request as GRequest
                creds.refresh(GRequest())
                creds_dict = {
                    'token': creds.token,
                    'refresh_token': creds.refresh_token,
                    'token_uri': creds.token_uri,
                    'client_id': creds.client_id,
                    'client_secret': creds.client_secret,
                    'scopes': creds.scopes
                }
                with open(_DEFAULT_TOKEN_PATH, 'w') as f:
                    json.dump(creds_dict, f)
            
            from googleapiclient.discovery import build
            service = build("drive", "v3", credentials=creds, cache_discovery=False)
            about = service.about().get(fields="user").execute()
            email = about.get("user", {}).get("emailAddress", "Cuenta Vinculada")
        except Exception as e:
            log.warning(f"No se pudo obtener el email de Google Drive: {e}")
            
        return {"authorized": True, "email": email}
    except Exception:
        return {"authorized": False}

@router.delete("/google/disconnect")
def disconnect_drive():
    """Elimina el token guardado para desvincular la cuenta."""
    try:
        if _DEFAULT_TOKEN_PATH.exists():
            os.remove(_DEFAULT_TOKEN_PATH)
        return {"success": True, "message": "Cuenta desvinculada correctamente."}
    except Exception as e:
        log.error(f"Error al desvincular Google Drive: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/google/login")
def login(request: Request):
    """Inicia el flujo de OAuth2 para vincular Google Drive."""
    redirect_uri = str(request.base_url).rstrip("/") + "/api/v1/auth/google/callback"
    flow = _get_flow(redirect_uri)
    
    auth_url, state = flow.authorization_url(
        access_type='offline',
        prompt='consent',
        include_granted_scopes='true'
    )
    
    if hasattr(flow, 'code_verifier'):
        _OAUTH_STORE[state] = flow.code_verifier
        
    return RedirectResponse(auth_url)

@router.get("/google/callback")
def callback(request: Request, state: str = None, code: str = None, error: str = None):
    """Recibe la autorización de Google y guarda el token maestro en la tienda."""
    if error:
        return HTMLResponse(f"<h2>Error de Autorización: {error}</h2><script>window.close()</script>")
    if not code:
        return HTMLResponse("<h2>Error: Google no ha devuelto ningún código.</h2><script>window.close()</script>")
        
    redirect_uri = str(request.base_url).rstrip("/") + "/api/v1/auth/google/callback"
    flow = _get_flow(redirect_uri)
    
    code_verifier = _OAUTH_STORE.get(state)
    if code_verifier:
        flow.code_verifier = code_verifier
        del _OAUTH_STORE[state]
    
    authorization_response = str(request.url)
    
    try:
        flow.fetch_token(authorization_response=authorization_response)
        creds = flow.credentials
        
        creds_dict = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes
        }
        with open(_DEFAULT_TOKEN_PATH, 'w') as f:
            json.dump(creds_dict, f)
            
        return HTMLResponse("""
        <html>
            <body style="display:flex; justify-content:center; align-items:center; height:100vh; font-family:sans-serif; background-color:#f8fafc;">
                <div style="text-align:center; padding:2rem; background:white; border-radius:12px; box-shadow:0 4px 6px -1px rgb(0 0 0 / 0.1);">
                    <h2 style="color: #10b981; margin-bottom: 1rem;">✅ ¡Vinculación Exitosa!</h2>
                    <p style="color: #64748b;">La cuenta de Google Drive ha sido conectada con la tienda.</p>
                    <p style="color: #94a3b8; font-size:0.875rem;">Cerrando pestaña automáticamente...</p>
                </div>
                <script>
                    window.opener.postMessage("GOOGLE_AUTH_SUCCESS", "*");
                    setTimeout(() => window.close(), 1500);
                </script>
            </body>
        </html>
        """)
    except Exception as e:
        log.error(f"Error de OAuth2: {e}")
        return HTMLResponse(f"<h2>Ocurrió un error al vincular la cuenta: {e}</h2>")

@router.get("/google/token")
def get_token():
    """Devuelve un token de acceso temporal para el frontend (Google Picker)."""
    if not _DEFAULT_TOKEN_PATH.exists():
        raise HTTPException(status_code=401, detail="No autorizado")
    
    try:
        with open(_DEFAULT_TOKEN_PATH, 'r') as f:
            creds_data = json.load(f)
        creds = Credentials.from_authorized_user_info(creds_data, SCOPES)
        
        if creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request as GRequest
            creds.refresh(GRequest())
            creds_dict = {
                'token': creds.token,
                'refresh_token': creds.refresh_token,
                'token_uri': creds.token_uri,
                'client_id': creds.client_id,
                'client_secret': creds.client_secret,
                'scopes': creds.scopes
            }
            with open(_DEFAULT_TOKEN_PATH, 'w') as f:
                json.dump(creds_dict, f)
                
        return {"access_token": creds.token, "client_id": creds.client_id}
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))
