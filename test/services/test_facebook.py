import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import requests

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.services.facebook import FacebookService, _mask_token, post_facebook_video


_CONFIG_FB_BASE = {
    "facebook_enabled": True,
    "facebook_page_id": "123456789012345",
    "facebook_access_token": "EAABsb123456789fakeaccesstoken",
    "facebook_auto_upload": True,
}


def _mock_fb_response(status_code=200, json_data=None):
    r = MagicMock()
    r.status_code = status_code
    r.content = b"true"
    r.json.return_value = json_data or {"id": "fb_video_999", "post_id": "12345_fb_video_999"}
    return r


class TestFacebookService(unittest.TestCase):
    def test_mask_token(self):
        self.assertEqual(_mask_token(""), "***")
        self.assertEqual(_mask_token("short"), "***")
        self.assertEqual(_mask_token("EAABsb123456789"), "EAAB...6789")

    @patch("app.services.facebook.config.app", {**_CONFIG_FB_BASE, "facebook_enabled": False})
    def test_unconfigured_service_skips_request(self):
        result = FacebookService().upload_video("/fake/v.mp4", "Title")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Facebook not configured")

    @patch("app.services.facebook.config.app", {**_CONFIG_FB_BASE, "facebook_page_id": "invalid_page_id_with_letters"})
    @patch("app.services.facebook.os.path.exists", return_value=True)
    def test_invalid_page_id_rejected(self, _exists):
        result = FacebookService().upload_video("/fake/v.mp4", "Title")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Invalid Facebook page_id format")

    @patch("app.services.facebook.config.app", _CONFIG_FB_BASE)
    @patch("app.services.facebook.os.path.exists", return_value=False)
    def test_missing_video_skips_request(self, _exists):
        result = FacebookService().upload_video("/missing/v.mp4", "Title")
        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"])

    @patch("app.services.facebook.config.app", _CONFIG_FB_BASE)
    @patch("app.services.facebook.os.path.exists", return_value=True)
    @patch("builtins.open", mock_open(read_data=b"fake video data"))
    @patch("app.services.facebook.requests.post")
    def test_successful_upload(self, mock_post, _exists):
        mock_post.return_value = _mock_fb_response(200, {"id": "1001", "post_id": "12345_1001"})

        result = post_facebook_video("/fake/v.mp4", title="My Title", description="My Description")
        self.assertTrue(result["success"])
        self.assertEqual(result["video_id"], "1001")
        self.assertEqual(result["platform"], "facebook")

        # Verify secure Authorization header usage (not token in query params)
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer EAABsb123456789fakeaccesstoken")
        self.assertNotIn("access_token", args[0])

    @patch("app.services.facebook.config.app", _CONFIG_FB_BASE)
    @patch("app.services.facebook.os.path.exists", return_value=True)
    @patch("builtins.open", mock_open(read_data=b"fake video data"))
    @patch("app.services.facebook.requests.post")
    def test_api_error_returns_clean_dict(self, mock_post, _exists):
        error_resp = MagicMock()
        error_resp.status_code = 400
        error_resp.content = b'{"error":{"message":"Invalid OAuth access token"}}'
        error_resp.json.return_value = {"error": {"message": "Invalid OAuth access token"}}
        mock_post.return_value = error_resp

        result = FacebookService().upload_video("/fake/v.mp4", "Title")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "Invalid OAuth access token")

    @patch("app.services.facebook.config.app", _CONFIG_FB_BASE)
    @patch("app.services.facebook.os.path.exists", return_value=True)
    @patch("builtins.open", mock_open(read_data=b"fake video data"))
    @patch("app.services.facebook.requests.post")
    def test_request_timeout_handled(self, mock_post, _exists):
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")
        result = FacebookService().upload_video("/fake/v.mp4", "Title")
        self.assertFalse(result["success"])
        self.assertIn("Connection timed out", result["error"])


if __name__ == "__main__":
    unittest.main()
