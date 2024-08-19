# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========
# Licensed under the Apache License, Version 2.0 (the “License”);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an “AS IS” BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =========== Copyright 2023 @ CAMEL-AI.org. All Rights Reserved. ===========

import os
import datetime
from http import HTTPStatus
from typing import List, Optional, Tuple, Union

import requests
from camel.toolkits import OpenAIFunction
from camel.toolkits.base import BaseToolkit

LINKEDIN_POST_LIMIT = 1300


class LinkedInToolkit(BaseToolkit):
    r"""A class representing a toolkit for LinkedIn operations.

    This class provides methods for creating a post, deleting a post, and
    retrieving the authenticated user's profile information.
    """

    def create_post(
        self,
        *,
        text: str,
        media_url: Optional[str] = None,
        article_url: Optional[str] = None,
    ) -> str:
        r"""Creates a new LinkedIn post.

        This function sends a POST request to the LinkedIn API to create a new
        post. The post can be text-only, or optionally include media or an article URL.
        A confirmation prompt is presented to the user before the post is created.

        Args:
            text (str): The text of the post. LinkedIn allows up to 1300 characters
                for a single post.
            media_url (Optional[str]): URL to media (image or video) to include in the post.
            article_url (Optional[str]): URL to an article to share.

        Returns:
            str: A message indicating the success of the post creation,
                including the post ID and text. If the request to the
                LinkedIn API is not successful, the return is an error message.

        Reference:
            https://docs.microsoft.com/en-us/linkedin/marketing/integrations/community-management/shares/ugc-post-api
        """
        if text is None:
            return "Text cannot be None"
        elif len(text) > LINKEDIN_POST_LIMIT:
            return "Text must not exceed 1300 characters."

        params = {
            "text": text,
            "media_url": media_url,
            "article_url": article_url,
        }
        print("You are going to create a LinkedIn post with the following parameters:")
        for key, value in params.items():
            if value is not None:
                print(f"{key}: {value}")

        confirm = input(
            "Are you sure you want to create this post? (yes/no): "
        )
        if confirm.lower() != "yes":
            return "Execution cancelled by the user."

        access_token = self._get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        post_data = {
            "author": f"urn:li:person:{self.get_my_profile_id()}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": text
                    },
                    "shareMediaCategory": "NONE" if media_url is None else "IMAGE",
                    "media": [] if media_url is None else [{"status": "READY", "originalUrl": media_url}],
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }

        if article_url is not None:
            post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "ARTICLE"
            post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["media"].append({
                "status": "READY",
                "originalUrl": article_url,
                "title": "Shared Article"
            })

        response = requests.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers=headers,
            json=post_data,
        )

        if response.status_code != HTTPStatus.CREATED:
            error_type = self._handle_http_error(response)
            return (
                "Request returned a(n) "
                + str(error_type)
                + ": "
                + str(response.status_code)
                + " "
                + response.text
            )

        json_response = response.json()
        post_id = json_response.get("id", "Unknown")
        return f"Post created successfully. Post ID: {post_id}. Text: '{text}'."

    def delete_post(self, post_id: str) -> str:
        r"""Deletes a LinkedIn post with the specified ID for an authorized user.

        This function sends a DELETE request to the LinkedIn API to delete
        a post with the specified ID. Before sending the request, it
        prompts the user to confirm the deletion.

        Args:
            post_id (str): The ID of the post to delete.

        Returns:
            str: A message indicating the result of the deletion. If the
                deletion was successful, the message includes the ID of the
                deleted post. If the deletion was not successful, the message
                includes an error message.

        Reference:
            https://docs.microsoft.com/en-us/linkedin/marketing/integrations/community-management/shares/ugc-post-api
        """
        if post_id is None:
            return "Post ID cannot be None"

        print(f"You are going to delete a LinkedIn post with the following ID: {post_id}")

        confirm = input(
            "Are you sure you want to delete this post? (yes/no): "
        )
        if confirm.lower() != "yes":
            return "Execution cancelled by the user."

        access_token = self._get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        response = requests.delete(
            f"https://api.linkedin.com/v2/ugcPosts/{post_id}",
            headers=headers,
        )

        if response.status_code != HTTPStatus.NO_CONTENT:
            error_type = self._handle_http_error(response)
            return (
                "Request returned a(n) "
                + str(error_type)
                + ": "
                + str(response.status_code)
                + " "
                + response.text
            )

        return f"Post deleted successfully. Post ID: {post_id}."

    def get_my_profile(self) -> str:
        r"""Retrieves and formats the authenticated user's LinkedIn
        profile info.

        This function sends a GET request to the LinkedIn API to retrieve the
        authenticated user's profile information. It then formats this information
        into a readable report.

        Returns:
            str: A formatted report of the authenticated user's LinkedIn profile
                information. This includes their ID, first name, last name, headline,
                and profile picture. If the request to the LinkedIn API is not
                successful, the return is an error message.

        Reference:
            https://docs.microsoft.com/en-us/linkedin/shared/references/v2/profile/basic-profile
        """
        access_token = self._get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        response = requests.get(
            "https://api.linkedin.com/v2/me",
            headers=headers,
        )

        if response.status_code != HTTPStatus.OK:
            error_type = self._handle_http_error(response)
            return (
                "Request returned a(n) "
                + str(error_type)
                + ": "
                + str(response.status_code)
                + " "
                + response.text
            )

        json_response = response.json()

        profile_report = (
            f"ID: {json_response.get('id')}. "
            f"First Name: {json_response.get('localizedFirstName')}. "
            f"Last Name: {json_response.get('localizedLastName')}. "
            f"Headline: {json_response.get('headline')}. "
        )

        profile_picture = json_response.get('profilePicture', {}).get('displayImage~', {}).get('elements', [{}])[-1]
        if profile_picture:
            profile_report += f"Profile Picture: {profile_picture.get('identifiers', [{}])[0].get('identifier', '')}. "

        return profile_report

    def get_my_profile_id(self) -> str:
        r"""Retrieves the authenticated user's LinkedIn profile ID.

        Returns:
            str: The LinkedIn profile ID of the authenticated user.
        """
        access_token = self._get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        response = requests.get(
            "https://api.linkedin.com/v2/me",
            headers=headers,
        )

        if response.status_code != HTTPStatus.OK:
            return ""

        json_response = response.json()
        return json_response.get('id', '')

    def _get_access_token(self) -> str:
        r"""Fetches the access token required for making LinkedIn API requests.

        Returns:
            str: The OAuth 2.0 access token.

        Note:
            This function assumes the existence of an environment variable
            `LINKEDIN_ACCESS_TOKEN` which stores the access token.
        """
        return os.getenv("LINKEDIN_ACCESS_TOKEN", "")

    def _handle_http_error(self, response: requests.Response) -> str:
        r"""Handles the HTTP errors based on the status code of the response.

        Args:
            response (requests.Response): The HTTP response from the API call.

        Returns:
            str: The error type, based on the status code.
        """
        if response.status_code == HTTPStatus.UNAUTHORIZED:
            return "Unauthorized. Check your access token."
        elif response.status_code == HTTPStatus.FORBIDDEN:
            return "Forbidden. You do not have permission to perform this action."
        elif response.status_code == HTTPStatus.NOT_FOUND:
            return "Not Found. The resource could not be located."
        elif response.status_code == HTTPStatus.TOO_MANY_REQUESTS:
            return "Too Many Requests. You have hit the rate limit."
        else:
            return "HTTP Error"