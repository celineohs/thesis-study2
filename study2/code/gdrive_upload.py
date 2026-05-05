# -*- coding: utf-8 -*-
"""
Google Drive 업로드 유틸 (Study1 대화 로그 / Study2 스레드 로그용).

지원 방식
- OAuth (권장, Shared drives 없이도 가능): 사용자의 Google Drive 용량 사용
  - GOOGLE_DRIVE_FOLDER_ID
  - GOOGLE_DRIVE_OAUTH_CLIENT_ID
  - GOOGLE_DRIVE_OAUTH_CLIENT_SECRET
  - GOOGLE_DRIVE_OAUTH_REFRESH_TOKEN

- Service Account (Shared drives 필요할 수 있음):
  - GOOGLE_DRIVE_FOLDER_ID
  - GOOGLE_DRIVE_CREDENTIALS_JSON

get_env(key)는 st.secrets / os.getenv 를 쓰는 앱의 _get_env 함수를 넘기면 됨.
"""

import json
import logging
import os
import re
import time
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _http_error_detail(exc: BaseException) -> str:
    """googleapiclient.errors.HttpError 본문을 짧은 문자열로."""
    try:
        from googleapiclient.errors import HttpError

        if isinstance(exc, HttpError):
            try:
                body = json.loads(exc.content.decode("utf-8", errors="replace"))
                err = body.get("error", {})
                msg = err.get("message") or str(body)
            except Exception:
                msg = exc.content.decode("utf-8", errors="replace")[:500]
            return f"HTTP {exc.resp.status}: {msg}"
    except Exception:
        pass
    return str(exc)


def _drive_upload_with_retry(create_callable, max_attempts: int = 3):
    """Drive API 일시 오류(429, 5xx)에 대해 짧게 재시도."""
    from googleapiclient.errors import HttpError

    last = None
    for attempt in range(max_attempts):
        try:
            return create_callable().execute()
        except HttpError as e:
            last = e
            status = getattr(e.resp, "status", None)
            if status in (429, 500, 502, 503, 504) and attempt + 1 < max_attempts:
                wait = 1.5 * (2**attempt)
                logger.warning(
                    "Drive API 재시도(%s/%s) %ss 후: %s",
                    attempt + 1,
                    max_attempts,
                    wait,
                    _http_error_detail(e),
                )
                time.sleep(wait)
                continue
            raise
    if last:
        raise last


def _get_oauth_credentials(get_env) -> Optional[object]:
    # Streamlit Secret 등 비문자 타입 대비
    client_id = str(get_env("GOOGLE_DRIVE_OAUTH_CLIENT_ID") or "").strip()
    client_secret = str(get_env("GOOGLE_DRIVE_OAUTH_CLIENT_SECRET") or "").strip()
    refresh_token = str(get_env("GOOGLE_DRIVE_OAUTH_REFRESH_TOKEN") or "").strip()
    if not (client_id and client_secret and refresh_token):
        return None

    try:
        from google.oauth2.credentials import Credentials
    except ImportError:
        return None

    return Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=_DRIVE_SCOPES,
    )


def _get_service_account_credentials(get_env) -> Tuple[Optional[object], Optional[str]]:
    creds_json = (get_env("GOOGLE_DRIVE_CREDENTIALS_JSON") or "").strip()
    # TOML """ 사용 시 맨 앞에 줄바꿈/BOM이 붙으면 "line 2 column 1" 파싱 오류 → 제거
    creds_json = creds_json.lstrip("\n\r\t \ufeff").rstrip("\n\r\t ")
    if not creds_json:
        return None, "GOOGLE_DRIVE_CREDENTIALS_JSON 미설정"

    try:
        import google.oauth2.service_account as sa
    except ImportError as e:
        return None, f"패키지 없음: {e}. pip install google-auth google-api-python-client"

    try:
        creds_dict = json.loads(creds_json)
    except json.JSONDecodeError as e:
        err_msg = str(e)
        creds_dict = None
        if "control character" in err_msg.lower():
            fixed = creds_json.replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n")
            try:
                creds_dict = json.loads(fixed)
            except json.JSONDecodeError:
                pass
        if creds_dict is None and ("Expecting property name" in err_msg or "line 2 column 1" in err_msg):
            fixed = re.sub(r"^\{\s+", "{", creds_json, count=1)
            if fixed != creds_json:
                try:
                    creds_dict = json.loads(fixed)
                except json.JSONDecodeError:
                    pass
        if creds_dict is None:
            return None, (
                f"GOOGLE_DRIVE_CREDENTIALS_JSON JSON 파싱 실패: {e}. "
                "Secrets에는 JSON을 한 줄로 넣고 키 이름은 쌍따옴표(\")를 사용하세요."
            )

    try:
        return sa.Credentials.from_service_account_info(creds_dict), None
    except Exception as e:
        return None, f"서비스 계정 credentials 생성 실패: {e}"


def upload_file_to_drive(file_path: str, get_env) -> tuple:
    """
    file_path 의 파일을 설정된 Google Drive 폴더에 업로드한다.
    get_env: (key: str, default=None) -> str 형태의 함수 (예: 앱의 _get_env)
    반환: (성공 여부, 메시지)
    """
    folder_id = str(get_env("GOOGLE_DRIVE_FOLDER_ID") or "").strip()
    if not folder_id:
        return False, "GOOGLE_DRIVE_FOLDER_ID 미설정"

    if not os.path.isfile(file_path):
        return False, f"파일 없음: {file_path}"

    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError as e:
        return False, f"패키지 없음: {e}. pip install google-auth google-api-python-client"

    # 1) OAuth 우선 (Shared drives 없어도 사용자 Drive 용량 사용)
    oauth_creds = _get_oauth_credentials(get_env)
    if oauth_creds is not None:
        try:
            from google.auth.exceptions import RefreshError
            from google.auth.transport.requests import Request

            # access_token 이 없으면 refresh (invalid_grant 등은 여기서 명확히 난다)
            if not oauth_creds.valid:
                oauth_creds.refresh(Request())

            service = build("drive", "v3", credentials=oauth_creds)
            file_name = os.path.basename(file_path)
            metadata = {"name": file_name, "parents": [folder_id]}

            def _create():
                media = MediaFileUpload(file_path, mimetype="application/json", resumable=True)
                return service.files().create(
                    body=metadata,
                    media_body=media,
                    fields="id",
                    supportsAllDrives=True,
                )

            # Shared Drive 폴더 업로드 호환: supportsAllDrives=True
            _drive_upload_with_retry(_create)
            return True, "Google Drive 업로드 완료 (OAuth)"
        except RefreshError as e:
            hint = (
                " refresh_token 이 만료·폐기되었거나 OAuth 클라이언트가 바뀌었을 수 있습니다. "
                "generate_drive_refresh_token.py 로 다시 발급하거나, "
                "Cloud Console에서 동의 화면이 '테스트'면 7일 후 토큰이 무효화될 수 있습니다(앱 게시 또는 재인증)."
            )
            msg = f"Google Drive OAuth 토큰 갱신 실패: {e}.{hint}"
            logger.error(msg)
            return False, msg
        except Exception as e:
            from googleapiclient.errors import HttpError

            detail = _http_error_detail(e)
            if isinstance(e, HttpError):
                if e.resp.status == 404:
                    detail += (
                        " — 폴더 ID가 잘못됐거나, 해당 폴더에 접근할 수 없습니다. "
                        "GOOGLE_DRIVE_FOLDER_ID 를 브라우저 주소창의 폴더 id 와 일치하는지 확인하세요."
                    )
                elif e.resp.status == 403:
                    detail += (
                        " — 이 Google 계정에 폴더에 대한 쓰기 권한이 없거나, "
                        "drive.file 범위로는 부모 폴더에 파일을 추가할 수 없는 경우가 있습니다. "
                        "폴더를 본인 My Drive 아래에 두고 다시 시도하세요."
                    )
            msg = f"Google Drive 업로드 실패(OAuth): {detail}"
            logger.exception("Google Drive upload (OAuth) failed: %s", detail)
            return False, msg

    # 2) Service Account fallback
    sa_creds, sa_err = _get_service_account_credentials(get_env)
    if sa_creds is None:
        return False, sa_err or "Google Drive 인증 미설정"

    try:
        from google.auth.transport.requests import Request
        from googleapiclient.errors import HttpError

        if hasattr(sa_creds, "refresh") and not sa_creds.valid:
            sa_creds.refresh(Request())

        service = build("drive", "v3", credentials=sa_creds)
        file_name = os.path.basename(file_path)
        metadata = {"name": file_name, "parents": [folder_id]}

        def _create_sa():
            media = MediaFileUpload(file_path, mimetype="application/json", resumable=True)
            return service.files().create(
                body=metadata,
                media_body=media,
                fields="id",
                supportsAllDrives=True,
            )

        _drive_upload_with_retry(_create_sa)
        return True, "Google Drive 업로드 완료 (Service Account)"
    except Exception as e:
        from googleapiclient.errors import HttpError

        detail = _http_error_detail(e)
        if isinstance(e, HttpError):
            if e.resp.status == 404:
                detail += (
                    " — 폴더 ID 오류이거나 서비스 계정에 폴더가 공유되지 않았습니다. "
                    "폴더를 서비스 계정 이메일(…@….iam.gserviceaccount.com)에 편집자로 공유하세요."
                )
            elif e.resp.status == 403:
                detail += " — 서비스 계정에 폴더 쓰기 권한이 없을 수 있습니다."
        msg = f"Google Drive 업로드 실패(Service Account): {detail}"
        logger.exception("Google Drive upload (Service Account) failed: %s", detail)
        return False, msg


def verify_drive_credentials(get_env) -> Tuple[bool, str]:
    """
    OAuth refresh_token 또는 서비스 계정 키로 access_token 발급이 되는지 확인한다.
    (업로드 자체는 하지 않음 — 로컬에서 .env 로 점검할 때 사용.)

    get_env: 앱의 _get_env 와 동일한 시그니처. 로컬 점검 시::

        import os
        verify_drive_credentials(os.getenv)
    """
    try:
        from google.auth.exceptions import RefreshError
        from google.auth.transport.requests import Request
    except ImportError as e:
        return False, f"패키지 없음: {e}"

    oauth = _get_oauth_credentials(get_env)
    if oauth is not None:
        try:
            if not oauth.valid:
                oauth.refresh(Request())
            return True, "OAuth: refresh_token 으로 access_token 발급 성공."
        except RefreshError as e:
            return (
                False,
                f"OAuth refresh 실패(invalid_grant 등): {e}. "
                "generate_drive_refresh_token.py 로 재발급하거나, "
                "OAuth 동의 화면이 '테스트'인 경우 7일마다 무효화될 수 있습니다.",
            )
        except Exception as e:
            return False, f"OAuth 오류: {e}"

    sa_creds, sa_err = _get_service_account_credentials(get_env)
    if sa_creds is not None:
        try:
            if hasattr(sa_creds, "refresh") and not sa_creds.valid:
                sa_creds.refresh(Request())
            return True, "Service Account: 자격 증명 유효."
        except Exception as e:
            return False, f"Service Account 오류: {e}"

    return (
        False,
        "Drive 인증 없음: OAuth 는 CLIENT_ID·CLIENT_SECRET·REFRESH_TOKEN 세 가지가 모두 있어야 하고, "
        "또는 GOOGLE_DRIVE_CREDENTIALS_JSON(서비스 계정)을 설정하세요.",
    )
