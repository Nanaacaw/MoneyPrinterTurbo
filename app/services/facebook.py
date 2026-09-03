"""
Facebook Graph API integration for posting videos/reels to Facebook Pages.
Docs: https://developers.facebook.com/docs/video-api/guides/publishing
"""
import os
import re

import requests
from loguru import logger
from app.config import config


def _mask_token(token: str) -> str:
    if not token or len(token) < 8:
        return "***"
    return f"{token[:4]}...{token[-4:]}"


class FacebookService:
    GRAPH_API_BASE = "https://graph.facebook.com/v21.0"

    @property
    def page_id(self) -> str:
        return str(config.app.get("facebook_page_id", "") or "").strip()

    @property
    def access_token(self) -> str:
        return str(config.app.get("facebook_access_token", "") or "").strip()

    @property
    def enabled(self) -> bool:
        return bool(config.app.get("facebook_enabled", False))

    @property
    def auto_upload(self) -> bool:
        return bool(config.app.get("facebook_auto_upload", False))

    def is_configured(self) -> bool:
        # Secure check: ensure page_id is alphanumeric/valid and token is present
        return bool(self.enabled and self.page_id and self.access_token)

    def upload_video(
        self,
        video_path: str,
        title: str = "",
        description: str = "",
    ) -> dict:
        """
        Uploads a video to Facebook Page via Graph API.
        ponytail: single POST multipart upload; add chunked resumable upload when video > 1GB.
        """
        if not self.is_configured():
            logger.warning("Facebook auto-posting is not configured or disabled.")
            return {"success": False, "error": "Facebook not configured"}

        if not os.path.exists(video_path):
            logger.error(f"Video file not found for Facebook upload: {video_path}")
            return {"success": False, "error": f"Video file not found: {video_path}"}

        # Validate page_id format (numbers only to prevent URL injection)
        if not re.match(r"^\d+$", self.page_id):
            logger.error("Invalid Facebook page_id format. Must be numeric.")
            return {"success": False, "error": "Invalid Facebook page_id format"}

        endpoint = f"{self.GRAPH_API_BASE}/{self.page_id}/videos"
        caption = description or title or "New Video"

        logger.info(
            f"Posting video to Facebook Page {self.page_id} (token: {_mask_token(self.access_token)})..."
        )

        try:
            with open(video_path, "rb") as video_file:
                # Security: Pass access_token in Authorization header or data, not query param URL to avoid log leakage
                data = {
                    "description": caption[:5000],
                    "title": title[:255] if title else "",
                }
                headers = {
                    "Authorization": f"Bearer {self.access_token}"
                }
                files = {
                    "source": video_file
                }

                response = requests.post(
                    endpoint,
                    headers=headers,
                    data=data,
                    files=files,
                    timeout=300,
                )

                result = response.json() if response.content else {}

                if response.status_code == 200 and "id" in result:
                    video_id = result.get("id")
                    logger.success(f"Facebook video posted successfully! ID: {video_id}")
                    return {
                        "success": True,
                        "platform": "facebook",
                        "video_id": video_id,
                        "post_id": result.get("post_id", video_id),
                    }
                else:
                    error_msg = result.get("error", {}).get("message", response.text)
                    logger.warning(f"Facebook upload failed ({response.status_code}): {error_msg}")
                    return {
                        "success": False,
                        "platform": "facebook",
                        "error": error_msg,
                    }

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to upload video to Facebook: {str(e)}")
            return {"success": False, "platform": "facebook", "error": str(e)}
        except Exception as e:
            logger.error(f"Unexpected error during Facebook upload: {str(e)}")
            return {"success": False, "platform": "facebook", "error": str(e)}


facebook_service = FacebookService()


def post_facebook_video(
    video_path: str,
    title: str = "",
    description: str = "",
) -> dict:
    return facebook_service.upload_video(
        video_path=video_path,
        title=title,
        description=description,
    )
